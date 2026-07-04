"""WebSocket handler for real-time chat with security controls."""

from __future__ import annotations

import json
import time
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select

from app.config import settings
from app.core.auth import decode_token
from app.core.dependencies import is_token_blacklisted
from app.core.logging import get_logger
from app.core.rate_limiter import check_rate_limit
from app.core.security import sanitize_prompt
from app.database import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.llm import get_llm_service
from app.services.memory import MemoryService
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections with per-user connection limits."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        # Track connection timestamps for per-user rate limiting
        self._connection_counts: dict[str, int] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> bool:
        """Connect a user. Returns False if connection limit exceeded."""
        # Check per-user connection limit
        current_count = self._connection_counts.get(user_id, 0)
        if current_count >= settings.ws_max_connections_per_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Maximum concurrent connections exceeded",
            )
            return False

        await websocket.accept()
        self.active_connections[user_id] = websocket
        self._connection_counts[user_id] = current_count + 1
        return True

    def disconnect(self, user_id: str) -> None:
        self.active_connections.pop(user_id, None)
        current = self._connection_counts.get(user_id, 0)
        if current > 0:
            self._connection_counts[user_id] = current - 1

    async def send_json(self, user_id: str, data: dict) -> None:
        websocket = self.active_connections.get(user_id)
        if websocket is not None:
            await websocket.send_json(data)


manager = ConnectionManager()

# Track messages per second per user for rate limiting
_ws_message_timestamps: dict[str, list[float]] = {}


def _check_ws_rate_limit(user_id: str) -> bool:
    """Check WebSocket message rate limit (N messages per minute)."""
    now = time.time()
    window_start = now - 60

    timestamps = _ws_message_timestamps.get(user_id, [])
    timestamps = [t for t in timestamps if t > window_start]

    if len(timestamps) >= settings.ws_max_messages_per_minute:
        return False

    timestamps.append(now)
    _ws_message_timestamps[user_id] = timestamps
    return True


@router.websocket("/ws/v1/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat with LLM streaming."""
    user: User | None = None
    db_session = await async_session_factory().__aenter__()

    try:
        # First message must contain auth token
        data = await websocket.receive_text()

        # Enforce message size limit
        if len(data) > settings.ws_max_message_size:
            await websocket.close(
                code=status.WS_1009_MESSAGE_TOO_BIG,
                reason="Message exceeds maximum size",
            )
            return

        msg = json.loads(data)
        token = msg.get("token")

        if token is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")
            return

        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type"
                )
                return

            # Check token blacklist
            jti = payload.get("jti", f"{payload.get('sub', '')}:{payload.get('iat', 0)}")
            if await is_token_blacklisted(jti):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Token has been revoked"
                )
                return

            result = await db_session.execute(select(User).where(User.id == UUID(payload["sub"])))
            user = result.scalar_one_or_none()
            if user is None or user.deleted_at is not None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
                return
        except JWTError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        # Connect with connection limit check
        connected = await manager.connect(str(user.id), websocket)
        if not connected:
            return

        # Send confirmation
        await websocket.send_json({"type": "connected", "user_id": str(user.id)})

        llm_service = get_llm_service()
        tool_executor = ToolExecutor()

        async with websocket:
            while True:
                data = await websocket.receive_text()

                # Enforce message size limit
                if len(data) > settings.ws_max_message_size:
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"Message exceeds maximum size of {settings.ws_max_message_size} bytes",
                    })
                    continue

                msg = json.loads(data)

                # Rate limit messages per user
                if not _check_ws_rate_limit(str(user.id)):
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Rate limit exceeded. Please slow down.",
                    })
                    continue

                msg_type = msg.get("type", "message")

                if msg_type == "message":
                    content = msg.get("content", "")
                    conversation_id = msg.get("conversation_id")

                    # Sanitize user input
                    content = sanitize_prompt(content)

                    # Skip empty messages
                    if not content.strip():
                        await websocket.send_json({
                            "type": "error",
                            "detail": "Message cannot be empty",
                        })
                        continue

                    # Create or get conversation
                    if conversation_id:
                        result = await db_session.execute(
                            select(Conversation).where(
                                Conversation.id == UUID(conversation_id),
                                Conversation.user_id == user.id,
                                Conversation.deleted_at.is_(None),
                            )
                        )
                        conversation = result.scalar_one_or_none()
                        if conversation is None:
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "detail": "Conversation not found",
                                }
                            )
                            continue
                    else:
                        conversation = Conversation(user_id=user.id, title=content[:50])
                        db_session.add(conversation)
                        await db_session.flush()
                        await db_session.refresh(conversation)
                        await websocket.send_json(
                            {
                                "type": "conversation_created",
                                "conversation_id": str(conversation.id),
                                "title": conversation.title,
                            }
                        )

                    # Save user message
                    user_message = Message(
                        conversation_id=conversation.id,
                        role="user",
                        content=content,
                    )
                    db_session.add(user_message)

                    # Get conversation history
                    history_result = await db_session.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at.asc())
                    )
                    history = history_result.scalars().all()

                    # Build context for LLM
                    messages_for_llm = [{"role": m.role, "content": m.content} for m in history]

                    # Inject relevant memories as context
                    memory_service = MemoryService(db_session)
                    memory_context = await memory_service.get_relevant_context(
                        user_id=user.id,
                        query=content,
                    )
                    if memory_context:
                        messages_for_llm.insert(
                            0,
                            {
                                "role": "system",
                                "content": memory_context,
                            },
                        )
                        # Notify frontend that memories were recalled
                        await websocket.send_json(
                            {
                                "type": "memory_recall",
                                "detail": "Relevant context from past conversations injected",
                            }
                        )

                    # Stream response from LLM
                    full_response = ""
                    async for chunk in llm_service.stream_chat(
                        messages=messages_for_llm,
                        tools=tool_executor.get_tool_definitions(),
                    ):
                        if chunk["type"] == "content":
                            full_response += chunk["content"]
                            await websocket.send_json(
                                {
                                    "type": "chunk",
                                    "content": chunk["content"],
                                }
                            )
                        elif chunk["type"] == "tool_call":
                            await websocket.send_json(
                                {
                                    "type": "tool_call",
                                    "tool_call_id": chunk.get("id"),
                                    "tool_name": chunk.get("name"),
                                    "arguments": chunk.get("arguments"),
                                }
                            )
                            # Execute tool
                            result = await tool_executor.execute(
                                tool_name=chunk.get("name", ""),
                                arguments=chunk.get("arguments", {}),
                            )
                            await websocket.send_json(
                                {
                                    "type": "tool_result",
                                    "tool_call_id": chunk.get("id"),
                                    "result": result,
                                }
                            )
                        elif chunk["type"] == "error":
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "detail": chunk.get("content", "LLM error"),
                                }
                            )

                    # Save assistant message
                    if full_response:
                        assistant_message = Message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=full_response,
                        )
                        db_session.add(assistant_message)

                    # Update conversation timestamp
                    conversation.title = conversation.title or content[:50]

                    await db_session.commit()

                    await websocket.send_json(
                        {
                            "type": "done",
                            "conversation_id": str(conversation.id),
                        }
                    )

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        try:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON message"})
        except Exception:
            pass
    except Exception:
        try:
            await websocket.send_json({"type": "error", "detail": "Internal server error"})
        except Exception:
            pass
    finally:
        if user is not None:
            manager.disconnect(str(user.id))
        await db_session.close()
"""WebSocket handler for real-time chat."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select

from app.core.auth import decode_token
from app.database import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.llm import get_llm_service
from app.services.memory import MemoryService
from app.services.tool_executor import ToolExecutor

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        self.active_connections.pop(user_id, None)

    async def send_json(self, user_id: str, data: dict) -> None:
        websocket = self.active_connections.get(user_id)
        if websocket is not None:
            await websocket.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/v1/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat with LLM streaming."""
    user: User | None = None
    db_session = await async_session_factory().__aenter__()

    try:
        # First message must contain auth token
        data = await websocket.receive_text()
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
            result = await db_session.execute(select(User).where(User.id == UUID(payload["sub"])))
            user = result.scalar_one_or_none()
            if user is None or user.deleted_at is not None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
                return
        except JWTError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        await manager.connect(str(user.id), websocket)

        # Send confirmation
        await websocket.send_json({"type": "connected", "user_id": str(user.id)})

        llm_service = get_llm_service()
        tool_executor = ToolExecutor()

        async with websocket:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)

                msg_type = msg.get("type", "message")

                if msg_type == "message":
                    content = msg.get("content", "")
                    conversation_id = msg.get("conversation_id")

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
    except Exception:
        await websocket.send_json({"type": "error", "detail": "Internal server error"})
    finally:
        if user is not None:
            manager.disconnect(str(user.id))
        await db_session.close()

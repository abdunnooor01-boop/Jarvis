"""WebSocket handler for real-time chat with security controls."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select

from app.config import settings
from app.core.auth import decode_token
from app.core.dependencies import is_token_blacklisted
from app.core.logging import get_logger
from app.core.security import sanitize_prompt
from app.database import async_session_factory
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.llm import get_llm_service
from app.services.memory import MemoryService
from app.services.tool_executor import ToolExecutor
from app.services.tool_policy import (
    APPROVAL_TIMEOUT_SECONDS,
    MAX_TOOL_TURNS,
    ToolPolicyService,
    blocked_in_hosted_mode,
    tool_requires_approval,
)

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

        try:
            await websocket.accept()
        except RuntimeError:
            # Accept is already done by the calling endpoint — tolerate a
            # double-accept so connect() stays usable standalone too.
            pass
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


def _parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Normalize LLM tool arguments (JSON string or dict) to a dict."""
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _log_tool_execution(
    db_session: Any,
    user_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    status_code: str,
) -> None:
    """Write an audit-log entry for a tool execution (approved/denied/auto)."""
    db_session.add(
        AuditLog(
            event_type="tool_execution",
            actor_id=user_id,
            resource=tool_name,
            action="execute",
            status=status_code,
            details={"arguments": arguments},
        )
    )


async def _decide_tool_approval(
    websocket: WebSocket,
    db_session: Any,
    user_id: str,
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[bool, str]:
    """Decide whether a tool call may execute.

    Returns (approved, reason). The decision chain is:
      policy classification -> user allowlist -> owner approval over WS.
    """
    if not tool_requires_approval(tool_name, arguments):
        return True, "auto-approved by policy"

    policy = ToolPolicyService(db_session)
    if await policy.is_allowlisted(user_id, tool_name, arguments):
        return True, "allowlisted"

    proposal_id = str(uuid.uuid4())
    await websocket.send_json(
        {
            "type": "tool_proposal",
            "proposal_id": proposal_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "reason": "This action requires your approval",
        }
    )

    while True:
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(), timeout=APPROVAL_TIMEOUT_SECONDS
            )
        except TimeoutError:
            return False, "Approval request timed out — action not executed"
        except Exception:
            return False, "Connection lost — action not executed"

        try:
            decision = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON message"})
            continue

        if decision.get("type") == "ping":
            await websocket.send_json({"type": "pong"})
            continue

        if decision.get("type") != "tool_decision":
            # Not an approval decision — keep waiting (client busy).
            continue
        if decision.get("proposal_id") != proposal_id:
            continue

        if decision.get("decision") == "approve":
            if decision.get("remember"):
                await policy.add_allowlist_entry(
                    user_id=user_id,
                    tool_name=tool_name,
                    arguments=arguments,
                )
            return True, "approved by owner"
        return False, "Action denied by owner"


def _assistant_tool_message(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the assistant message with tool_calls for the LLM continuation."""
    message: dict[str, Any] = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": tc.get("id") or f"call_{i}",
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": tc.get("arguments", ""),
                },
            }
            for i, tc in enumerate(tool_calls)
        ],
    }
    return message


@router.websocket("/ws/v1/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat with LLM streaming."""
    user: User | None = None
    db_session = await async_session_factory().__aenter__()

    try:
        # Accept the WebSocket handshake BEFORE any receive — the first ASGI
        # message is websocket.connect, and receive_text() on it raises
        # KeyError: 'text' which would leave the handshake uncompleted.
        await websocket.accept()

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

        while True:
            data = await websocket.receive_text()

            # Enforce message size limit
            if len(data) > settings.ws_max_message_size:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Message exceeds maximum size of {settings.ws_max_message_size} bytes",
                })
                continue

            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                # Malformed JSON — send an error frame but KEEP the connection
                # open so the client can recover and send again.
                await websocket.send_json({
                    "type": "error",
                    "detail": "Invalid JSON message",
                })
                continue

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

                # Stream response from LLM — multi-turn tool loop with
                # approval gating: the model may emit tool calls, each is
                # approved/denied per policy + allowlist + owner decision,
                # results are fed back, and the model continues until it
                # produces a final answer.
                full_response = ""
                tool_definitions = tool_executor.get_tool_definitions()

                for _turn in range(MAX_TOOL_TURNS):
                    tool_calls: list[dict[str, Any]] = []
                    turn_error = False

                    async for chunk in llm_service.stream_chat(
                        messages=messages_for_llm,
                        tools=tool_definitions,
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
                            tool_calls.append(chunk)
                        elif chunk["type"] == "error":
                            turn_error = True
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "detail": chunk.get("content", "LLM error"),
                                }
                            )

                    if not tool_calls or turn_error:
                        break

                    # Let the model see the tool calls it just made.
                    messages_for_llm.append(_assistant_tool_message(tool_calls))

                    for tc in tool_calls:
                        tool_name = tc.get("name", "")
                        arguments = _parse_tool_arguments(tc.get("arguments"))
                        tool_call_id = tc.get("id") or str(uuid.uuid4())

                        await websocket.send_json(
                            {
                                "type": "tool_call",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "arguments": arguments,
                            }
                        )

                        # Hosted (web/cloud) mode: Jarvis has no local host
                        # access, so high-impact desktop-control tools can
                        # never run — regardless of allowlist or approval.
                        # Report them as unavailable and let the model explain.
                        if settings.jarvis_mode == "hosted" and blocked_in_hosted_mode(
                            tool_name, arguments
                        ):
                            _log_tool_execution(
                                db_session,
                                str(user.id),
                                tool_name,
                                arguments,
                                "blocked-hosted",
                            )
                            blocked_result = {
                                "status": "unavailable",
                                "reason": "hosted mode — action not executed",
                            }
                            await websocket.send_json(
                                {
                                    "type": "tool_result",
                                    "tool_call_id": tool_call_id,
                                    "tool_name": tool_name,
                                    "result": blocked_result,
                                    "unavailable": True,
                                }
                            )
                            messages_for_llm.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "content": json.dumps(blocked_result),
                                }
                            )
                            continue

                        approved, reason = await _decide_tool_approval(
                            websocket=websocket,
                            db_session=db_session,
                            user_id=str(user.id),
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                            arguments=arguments,
                        )

                        if approved:
                            result = await tool_executor.execute(
                                tool_name=tool_name,
                                arguments=arguments,
                            )
                            _log_tool_execution(
                                db_session, str(user.id), tool_name, arguments, "approved"
                            )
                            await websocket.send_json(
                                {
                                    "type": "tool_result",
                                    "tool_call_id": tool_call_id,
                                    "tool_name": tool_name,
                                    "result": result,
                                    "approval": reason,
                                }
                            )
                        else:
                            _log_tool_execution(
                                db_session, str(user.id), tool_name, arguments, "denied"
                            )
                            result = {"error": reason, "denied": True}
                            await websocket.send_json(
                                {
                                    "type": "tool_result",
                                    "tool_call_id": tool_call_id,
                                    "tool_name": tool_name,
                                    "result": result,
                                    "denied": True,
                                }
                            )

                        # Feed the outcome back so the model can continue.
                        messages_for_llm.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(result),
                            }
                        )

                    # Loop again — the model now sees the tool results.

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
        logger.warning("WS invalid JSON from user %s", getattr(user, "id", None))
        try:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON message"})
        except Exception:
            pass
    except Exception:
        logger.exception("WS internal error for user %s", getattr(user, "id", None))
        try:
            await websocket.send_json({"type": "error", "detail": "Internal server error"})
        except Exception:
            pass
    finally:
        if user is not None:
            manager.disconnect(str(user.id))
        await db_session.close()

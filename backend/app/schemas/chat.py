"""Chat-related Pydantic schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """Create a new conversation."""

    title: str = Field(default="New Conversation", max_length=255)


class ConversationResponse(BaseModel):
    """Conversation summary response."""

    id: UUID
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Message response."""

    id: UUID
    role: str
    content: str
    created_at: str


class ConversationDetailResponse(BaseModel):
    """Full conversation with messages."""

    id: UUID
    title: str
    messages: list[MessageResponse]
    created_at: str
    updated_at: str


class ChatMessageRequest(BaseModel):
    """WebSocket chat message payload."""

    conversation_id: str | None = None
    content: str
    stream: bool = True

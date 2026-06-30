"""Message ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Message(Base):
    """Chat message model."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        name="metadata",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role!r})>"
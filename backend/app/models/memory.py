"""Memory ORM model for long-term vector storage."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MemoryEntry(Base):
    """Long-term memory entry with vector embedding.

    Stores conversation summaries, user preferences, facts, and entities
    with semantic search via pgvector embeddings.

    The `embedding` column is defined as Text for maximum compatibility
    (PostgreSQL + SQLite). In production with PostgreSQL, an Alembic
    migration should alter this column to use pgvector's Vector(1536)
    type for native vector similarity search.
    """

    __tablename__ = "memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Stored as JSON-encoded list of floats (Text type for cross-dialect compat)
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<MemoryEntry(id={self.id}, type={self.type!r})>"
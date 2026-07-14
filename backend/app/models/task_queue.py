"""Task Queue Item ORM model — persisted tasks for server-side execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskQueueItem(Base):
    """A persisted task in the server-side task queue.

    Stores the task spec (type, params, metadata), execution status,
    results, and timestamps. Survives server restarts so mobile clients
    can submit tasks while offline and retrieve results on reconnect.
    """

    __tablename__ = "task_queue_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Task type: chat, browse, test, freelance, code, etc.",
    )
    params: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Task parameters (varies by task type)",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        name="metadata",
        comment="Optional metadata (source device, tags, etc.)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        index=True,
    )
    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-encoded result data when completed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Progress percentage (0-100)",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    source_device: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Device that submitted the task (ios, android, web, desktop)",
    )
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<TaskQueueItem(id={self.id}, type={self.task_type!r}, "
            f"status={self.status!r})>"
        )
"""FreelanceJob ORM model — represents a paid job for Jarvis's freelancer mode."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FreelanceJob(Base):
    """A paid job executed by Jarvis in freelancer mode.

    Each job has a specific task type (e.g., app testing, copywriting, web research)
    and goes through a lifecycle: pending → paid → in_progress → completed/failed → delivered.
    """

    __tablename__ = "freelance_jobs"

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
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    input_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )
    result_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    result_files: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    deliverable_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    def __repr__(self) -> str:
        return (
            f"<FreelanceJob(id={self.id}, type={self.task_type!r}, "
            f"status={self.status!r})>"
        )

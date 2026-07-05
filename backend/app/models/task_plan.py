"""Task Plan ORM model — represents a planned execution of steps to achieve a goal."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskPlan(Base):
    """A high-level task plan that breaks a user goal into discrete steps.

    Each plan belongs to a user and consists of multiple TaskSteps
    that are executed sequentially by the Task Execution Engine.
    """

    __tablename__ = "task_plans"

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
    goal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    total_steps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    completed_steps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_steps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )
    error_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="abort",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
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

    # Relationship
    steps: Mapped[list[TaskStep]] = relationship(
        "TaskStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="TaskStep.step_number",
    )

    def __repr__(self) -> str:
        return (
            f"<TaskPlan(id={self.id}, status={self.status!r}, "
            f"goal={self.goal[:50]!r})>"
        )
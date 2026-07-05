"""Task Plan and Task Step ORM models for autonomous task execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskPlan(Base):
    """A plan for autonomous multi-step task execution."""

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
        comment="The original user goal / request",
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Short auto-generated title for the plan",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | approved | running | paused | completed | failed | cancelled",
    )
    error_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="abort",
        comment="abort | skip | retry (default behaviour on step failure)",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        comment="Max retries per step on failure",
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
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    steps: Mapped[list[TaskStep]] = relationship(
        "TaskStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TaskStep.step_order",
    )

    def __repr__(self) -> str:
        return f"<TaskPlan(id={self.id}, status={self.status!r}, goal={self.goal[:50]!r})>"


class TaskStep(Base):
    """A single step within a TaskPlan."""

    __tablename__ = "task_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("task_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Execution order (0-based)",
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Name of the tool to call",
    )
    tool_params: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Parameters for the tool",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable description of this step",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | running | completed | failed | skipped | cancelled",
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Result returned by the tool",
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if step failed",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    plan: Mapped[TaskPlan] = relationship(
        "TaskPlan",
        back_populates="steps",
    )

    def __repr__(self) -> str:
        return (
            f"<TaskStep(id={self.id}, order={self.step_order}, "
            f"tool={self.tool_name!r}, status={self.status!r})>"
        )

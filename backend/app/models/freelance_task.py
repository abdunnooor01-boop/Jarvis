"""Freelance task ORM models — task templates and customer job orders."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskTemplate(Base):
    """A pre-defined task template with fixed pricing.

    Templates define what Jarvis can do as a freelancer (e.g., App Testing,
    Copywriting, Data Entry). Each template has a name, description, category,
    price, and estimated time.
    """

    __tablename__ = "freelance_task_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    estimated_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    required_capabilities: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<TaskTemplate(id={self.id}, name={self.name!r}, "
            f"price_cents={self.price_cents})>"
        )


class FreelanceJob(Base):
    """A customer job order for a freelance task.

    Created when a customer places an order for a task template.
    Tracks payment status, processing state, and deliverable results.
    """

    __tablename__ = "freelance_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("freelance_task_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )
    customer_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    stripe_payment_link: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    stripe_session_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    result_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    result_files: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<FreelanceJob(id={self.id}, template={self.template_id}, "
            f"status={self.status!r}, amount={self.amount_cents})>"
        )
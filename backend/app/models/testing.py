"""SaaS Testing Service ORM models — test plans, runs, and subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TestPlan(Base):
    """A test plan defines what to test, how often, and for which customer.

    Customers create test plans for their web applications. Each plan
    specifies the URL, test criteria, schedule, and current status.
    """

    __tablename__ = "test_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    test_criteria: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    schedule: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",  # manual, daily, weekly
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",  # active, paused, archived
        index=True,
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
            f"<TestPlan(id={self.id}, name={self.name!r}, "
            f"url={self.url!r}, status={self.status!r})>"
        )


class TestRun(Base):
    """A single execution of a test plan.

    Stores the results, screenshots, status, and timing of each test run.
    """

    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("test_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",  # pending, running, passed, failed, error
        index=True,
    )
    results_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    screenshots: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<TestRun(id={self.id}, plan_id={self.plan_id}, "
            f"status={self.status!r})>"
        )


class TestSubscription(Base):
    """A customer's SaaS testing subscription.

    Links a customer to a billing tier and Stripe subscription for
    recurring access to the testing service.
    """

    __tablename__ = "test_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="basic",  # basic, pro
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="incomplete",  # incomplete, active, past_due, canceled, expired
        index=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
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
            f"<TestSubscription(id={self.id}, tier={self.tier!r}, "
            f"status={self.status!r})>"
        )

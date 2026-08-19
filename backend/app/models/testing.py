"""SaaS Testing Service ORM models — test plans, runs, results, and subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    """A single execution of a test plan, containing results and metadata.

    Stores the results, screenshots, status, timing, and detailed test
    results (TestResult rows) for each test run.
    """

    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("test_plans.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        default=None,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    total_tests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    passed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    report_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    results: Mapped[list[TestResult]] = relationship(
        "TestResult",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="TestResult.step_number",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<TestRun(id={self.id}, status={self.status!r}, "
            f"url={self.url[:50]!r}, passed={self.passed}/{self.total_tests})>"
        )


class TestResult(Base):
    """A single test criterion result within a test run.

    Each result tests one aspect of a page (e.g. "the login button
    should be visible", "the page title should be 'Home'").
    """

    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    criterion: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    test_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="element_visibility",
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    screenshot_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    run: Mapped[TestRun] = relationship("TestRun", back_populates="results")

    def __repr__(self) -> str:
        return (
            f"<TestResult(id={self.id}, criterion={self.criterion[:40]!r}, "
            f"passed={self.passed})>"
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

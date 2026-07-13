"""TestRun and TestResult ORM models — represents a website QA test run and its results."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TestRun(Base):
    """A test run against a website URL.

    Contains multiple test criteria (TestResult rows) that each
    verify a specific aspect of the page (element visibility, text
    content, link behavior, etc.).
    """

    __tablename__ = "test_runs"

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

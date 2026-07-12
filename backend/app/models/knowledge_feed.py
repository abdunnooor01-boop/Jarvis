"""Knowledge feed ORM models — curated sources and ingested knowledge entries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KnowledgeSource(Base):
    """A curated source of knowledge that Jarvis periodically checks.

    Supports RSS feeds, API endpoints, and static web pages.
    Each source has a schedule for how often it should be fetched.
    """

    __tablename__ = "knowledge_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type of source: rss, api, or page",
    )
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    schedule: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Fetch schedule: hourly, daily, weekly",
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Content category (e.g., ai/ml, python, devtools)",
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_fetch_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Status of last fetch: success, error, never",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
            f"<KnowledgeSource(id={self.id}, name={self.name!r}, "
            f"type={self.source_type!r}, enabled={self.enabled})>"
        )


class KnowledgeEntry(Base):
    """A single knowledge entry ingested from a source.

    Stores the title, summary, content, and metadata for each item
    discovered by Jarvis's knowledge feed system.
    """

    __tablename__ = "knowledge_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full content body if available",
    )
    url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    relevance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="0.0 to 1.0 — how relevant this entry is to Jarvis's domains",
    )
    is_reviewed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    source_url_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 hash of source URL to detect duplicates",
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeEntry(id={self.id}, title={self.title!r}, "
            f"source={self.source_id}, score={self.relevance_score})>"
        )
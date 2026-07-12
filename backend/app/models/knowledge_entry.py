"""Knowledge Entry and Feed Source ORM models for knowledge feeds."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedSource(Base):
    """A curated source that the feed crawler periodically checks.

    Sources can be RSS/Atom feeds, API endpoints, or web scraping targets.
    Tracks last fetch time and error state for health monitoring.
    """

    __tablename__ = "feed_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type: hackernews, github_trending, rss, changelog",
    )
    url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="URL for RSS feeds or API endpoints",
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Extra config (e.g., language filter, topic filter)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    fetch_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message if fetch failed",
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<FeedSource(id={self.id}, name={self.name!r}, "
            f"type={self.source_type!r})>"
        )


class KnowledgeEntry(Base):
    """A knowledge item discovered from a feed source.

    Each entry stores the extracted information with its source attribution,
    ready for vector embedding and semantic search.
    """

    __tablename__ = "knowledge_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
        comment="FK to feed_sources.id (no FK constraint for resilience)",
    )
    source_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full content or extracted text",
    )
    author: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Original publication date from source",
    )
    topics: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Auto-categorised topics/tags",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        name="metadata",
        default=dict,
        comment="Extra metadata (score, points, comments, language)",
    )
    # Embedding for semantic search (stored as JSON-encoded list of floats)
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the user has seen/read this entry",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeEntry(id={self.id}, title={self.title!r}, "
            f"source={self.source_name!r})>"
        )

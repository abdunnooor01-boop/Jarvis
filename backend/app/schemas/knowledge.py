"""Pydantic schemas for knowledge feed sources and entries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Feed Source schemas
# ---------------------------------------------------------------------------


class FeedSourceCreate(BaseModel):
    """Schema for creating a new feed source."""

    name: str = Field(..., max_length=200, description="Unique source name")
    source_type: str = Field(
        ...,
        max_length=50,
        description="Type: hackernews, github_trending, rss, changelog",
    )
    url: str | None = Field(None, max_length=1000, description="URL for RSS/API")
    config: dict[str, Any] | None = Field(
        None,
        description="Extra config (language filter, topic filter)",
    )
    fetch_interval_minutes: int = Field(
        60,
        ge=1,
        le=10080,
        description="How often to poll this source (minutes)",
    )


class FeedSourceUpdate(BaseModel):
    """Schema for updating an existing feed source."""

    name: str | None = Field(None, max_length=200)
    source_type: str | None = Field(None, max_length=50)
    url: str | None = Field(None, max_length=1000)
    config: dict[str, Any] | None = None
    is_active: bool | None = None
    fetch_interval_minutes: int | None = Field(None, ge=1, le=10080)


class FeedSourceResponse(BaseModel):
    """Schema for feed source responses."""

    id: uuid.UUID
    name: str
    source_type: str
    url: str | None
    config: dict[str, Any] | None
    is_active: bool
    fetch_interval_minutes: int
    last_fetched_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedSourceListResponse(BaseModel):
    """Schema for listing feed sources."""

    items: list[FeedSourceResponse]
    total: int


# ---------------------------------------------------------------------------
# Knowledge Entry schemas
# ---------------------------------------------------------------------------


class KnowledgeEntryResponse(BaseModel):
    """Schema for knowledge entry responses."""

    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    title: str
    url: str | None
    summary: str | None
    content: str | None
    author: str | None
    published_at: datetime | None
    topics: list[str] | None
    metadata_: dict[str, Any] | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEntryListResponse(BaseModel):
    """Schema for listing knowledge entries."""

    items: list[KnowledgeEntryResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


# ---------------------------------------------------------------------------
# Crawl / Digest schemas
# ---------------------------------------------------------------------------


class CrawlResult(BaseModel):
    """Result of a single crawl operation."""

    source_id: str | None = None
    source_name: str
    entries_found: int = 0
    entries_stored: int = 0
    error: str | None = None


class CrawlResponse(BaseModel):
    """Response from a crawl operation."""

    results: list[CrawlResult]
    total_entries_found: int = 0
    total_entries_stored: int = 0


class DigestEntry(BaseModel):
    """A single entry in the knowledge digest."""

    title: str
    url: str | None
    source_name: str
    summary: str | None
    topics: list[str] | None


class DigestResponse(BaseModel):
    """Weekly knowledge digest."""

    generated_at: datetime
    total_entries: int
    entries: list[DigestEntry]


# ---------------------------------------------------------------------------
# Tool Discovery schemas
# ---------------------------------------------------------------------------


class DiscoveredTool(BaseModel):
    """A tool discovered from a knowledge entry."""

    entry_id: uuid.UUID
    title: str
    url: str | None
    description: str | None
    category: str | None = None
    confidence: str = Field(
        ...,
        pattern=r"^(high|medium|low)$",
        description="Confidence that this is a usable tool",
    )


class DiscoveryResult(BaseModel):
    """Result of a tool discovery scan."""

    entries_scanned: int
    tools_found: list[DiscoveredTool]
    scan_time_seconds: float

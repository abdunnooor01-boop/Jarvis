"""Pydantic schemas for knowledge feed sources and entries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeSourceCreate(BaseModel):
    """Request schema for creating a new knowledge source."""

    name: str = Field(..., max_length=200, description="Display name of the source")
    source_type: str = Field(
        ..., pattern=r"^(rss|api|page)$", description="Type: rss, api, or page"
    )
    url: str = Field(..., max_length=500, description="URL of the source")
    schedule: str = Field(
        "daily", pattern=r"^(hourly|daily|weekly)$", description="Fetch schedule"
    )
    category: str | None = Field(None, max_length=100, description="Content category")


class KnowledgeSourceResponse(BaseModel):
    """Response schema for a knowledge source."""

    id: UUID
    name: str
    source_type: str
    url: str
    schedule: str
    category: str | None = None
    last_fetched_at: str | None = None
    last_fetch_status: str | None = None
    enabled: bool = True
    created_at: str

    model_config = {"from_attributes": True}


class KnowledgeSourceListResponse(BaseModel):
    """Paginated list of knowledge sources."""

    items: list[KnowledgeSourceResponse]
    total: int


class KnowledgeEntryResponse(BaseModel):
    """Response schema for a knowledge entry."""

    id: UUID
    source_id: UUID
    source_name: str = ""
    title: str
    summary: str | None = None
    content: str | None = None
    url: str | None = None
    category: str | None = None
    tags: list[str] = []
    discovered_at: str
    relevance_score: float | None = None
    is_reviewed: bool = False

    model_config = {"from_attributes": True}


class KnowledgeEntryListResponse(BaseModel):
    """Paginated list of knowledge entries."""

    items: list[KnowledgeEntryResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1
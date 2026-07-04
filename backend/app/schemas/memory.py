"""Pydantic schemas for memory/vector search."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    """Create a new memory entry."""

    type: str = Field(..., pattern=r"^(conversation_summary|preference|fact|entity)$")
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] | None = None


class MemoryUpdate(BaseModel):
    """Update an existing memory entry."""

    content: str | None = None
    metadata: dict[str, Any] | None = None


class MemoryResponse(BaseModel):
    """Memory entry response."""

    id: UUID
    user_id: UUID
    type: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MemorySearchQuery(BaseModel):
    """Search query parameters."""

    q: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class MemorySearchResult(BaseModel):
    """Search result with relevance score."""

    memory: MemoryResponse
    score: float


class PreferenceUpdate(BaseModel):
    """Update user preferences."""

    preferences: dict[str, str]


class PreferenceResponse(BaseModel):
    """User preferences response."""

    preferences: dict[str, str]


class MemoryListResponse(BaseModel):
    """Paginated list of memories."""

    items: list[MemoryResponse]
    total: int
    page: int
    page_size: int
    pages: int
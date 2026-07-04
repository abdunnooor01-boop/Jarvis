"""Memory API routes for long-term storage and retrieval."""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.memory import (
    MemoryCreate,
    MemoryListResponse,
    MemoryResponse,
    MemorySearchResult,
    MemoryUpdate,
    PreferenceResponse,
    PreferenceUpdate,
)
from app.services.memory import MemoryService

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


def _memory_to_response(memory: Any) -> dict:
    """Convert a MemoryEntry ORM object to a response dict."""
    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "type": memory.type,
        "content": memory.content,
        "metadata": memory.metadata_,
        "created_at": memory.created_at.isoformat() if memory.created_at else "",
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else "",
    }


@router.get("/search", response_model=list[MemorySearchResult])
async def search_memories(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=5, ge=1, le=50),
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Search memories by semantic similarity."""
    service = MemoryService(db)
    results = await service.search_memories(
        user_id=current_user.id,
        query=q,
        limit=limit,
        threshold=threshold,
    )

    return [
        {
            "memory": _memory_to_response(r["memory"]),
            "score": r["score"],
        }
        for r in results
    ]


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    type: str | None = Query(default=None, description="Filter by memory type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List memories with pagination and optional type filter."""
    service = MemoryService(db)
    entries, total = await service.list_memories(
        user_id=current_user.id,
        type=type,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [_memory_to_response(e) for e in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)),
    }


@router.delete("/{memory_id}", status_code=status.HTTP_200_OK)
async def delete_memory(
    memory_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete a memory entry."""
    service = MemoryService(db)
    success = await service.delete_memory(memory_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory entry not found",
        )

    return {"detail": "Memory entry deleted"}


@router.post(
    "/conversations/{conversation_id}/summarize",
    status_code=status.HTTP_201_CREATED,
)
async def summarize_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger conversation summarization."""
    service = MemoryService(db)
    memory = await service.summarize_conversation(conversation_id)

    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or has no messages",
        )

    return _memory_to_response(memory)


@router.get("/preferences", response_model=PreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get all user preferences."""
    service = MemoryService(db)
    preferences = await service.get_user_preferences(current_user.id)
    return {"preferences": preferences}


@router.put("/preferences", response_model=PreferenceResponse)
async def update_preferences(
    body: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update user preferences."""
    service = MemoryService(db)

    for key, value in body.preferences.items():
        await service.store_user_preference(current_user.id, key, value)

    # Return all preferences after update
    preferences = await service.get_user_preferences(current_user.id)
    return {"preferences": preferences}
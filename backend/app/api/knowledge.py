"""Knowledge feed API — curated sources and ingested knowledge entries."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.knowledge_feed import KnowledgeEntry, KnowledgeSource
from app.models.user import User
from app.schemas.knowledge_feed import (
    KnowledgeEntryListResponse,
    KnowledgeEntryResponse,
    KnowledgeSourceCreate,
    KnowledgeSourceListResponse,
    KnowledgeSourceResponse,
)
from app.services.knowledge_seeder import ensure_knowledge_sources_seeded

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


async def _source_to_response(s: KnowledgeSource) -> KnowledgeSourceResponse:
    """Convert a KnowledgeSource ORM to response schema."""
    return KnowledgeSourceResponse(
        id=s.id,
        name=s.name,
        source_type=s.source_type,
        url=s.url,
        schedule=s.schedule,
        category=s.category,
        last_fetched_at=str(s.last_fetched_at) if s.last_fetched_at else None,
        last_fetch_status=s.last_fetch_status,
        enabled=s.enabled,
        created_at=str(s.created_at),
    )


async def _entry_to_response(
    entry: KnowledgeEntry, db: AsyncSession
) -> KnowledgeEntryResponse:
    """Convert a KnowledgeEntry ORM to response schema."""
    source_name = ""
    if entry.source_id:
        result = await db.execute(
            select(KnowledgeSource.name).where(KnowledgeSource.id == entry.source_id)
        )
        row = result.scalar_one_or_none()
        if row:
            source_name = row

    return KnowledgeEntryResponse(
        id=entry.id,
        source_id=entry.source_id,
        source_name=source_name,
        title=entry.title,
        summary=entry.summary,
        content=entry.content,
        url=entry.url,
        category=entry.category,
        tags=entry.tags or [],
        discovered_at=str(entry.discovered_at),
        relevance_score=entry.relevance_score,
        is_reviewed=entry.is_reviewed,
    )


@router.get("/sources", response_model=KnowledgeSourceListResponse)
async def list_sources(
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceListResponse:
    """List all knowledge sources (public)."""
    await ensure_knowledge_sources_seeded(db)

    result = await db.execute(
        select(KnowledgeSource).order_by(KnowledgeSource.name)
    )
    sources = result.scalars().all()

    return KnowledgeSourceListResponse(
        items=[await _source_to_response(s) for s in sources],
        total=len(sources),
    )


@router.get("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def get_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    """Get details of a specific knowledge source."""
    result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    return await _source_to_response(source)


@router.post(
    "/sources",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    body: KnowledgeSourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSourceResponse:
    """Create a new knowledge source (auth required)."""
    source = KnowledgeSource(
        id=uuid.uuid4(),
        name=body.name,
        source_type=body.source_type,
        url=body.url,
        schedule=body.schedule,
        category=body.category,
        last_fetch_status="never",
        enabled=True,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    logger.info("Knowledge source created", name=body.name, source_id=str(source.id))
    return await _source_to_response(source)


@router.get("/entries", response_model=KnowledgeEntryListResponse)
async def list_entries(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    source_id: uuid.UUID | None = Query(None, description="Filter by source"),
    category: str | None = Query(None, description="Filter by category"),
    unread_only: bool = Query(False, description="Only show unreviewed entries"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeEntryListResponse:
    """List knowledge entries with pagination and filtering (auth required)."""
    await ensure_knowledge_sources_seeded(db)

    query = select(KnowledgeEntry)
    count_query = select(func.count(KnowledgeEntry.id))

    if source_id:
        query = query.where(KnowledgeEntry.source_id == source_id)
        count_query = count_query.where(KnowledgeEntry.source_id == source_id)

    if category:
        query = query.where(KnowledgeEntry.category == category)
        count_query = count_query.where(KnowledgeEntry.category == category)

    if unread_only:
        query = query.where(KnowledgeEntry.is_reviewed == False)
        count_query = count_query.where(KnowledgeEntry.is_reviewed == False)

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(KnowledgeEntry.discovered_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    entries = result.scalars().all()

    items = [await _entry_to_response(e, db) for e in entries]
    pages = max(1, (total + page_size - 1) // page_size)

    return KnowledgeEntryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/entries/{entry_id}", response_model=KnowledgeEntryResponse)
async def get_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeEntryResponse:
    """Get details of a specific knowledge entry."""
    result = await db.execute(
        select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found",
        )

    return await _entry_to_response(entry, db)


@router.post("/entries/{entry_id}/review", response_model=KnowledgeEntryResponse)
async def mark_entry_reviewed(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeEntryResponse:
    """Mark a knowledge entry as reviewed (auth required)."""
    result = await db.execute(
        select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found",
        )

    entry.is_reviewed = True
    await db.commit()
    await db.refresh(entry)

    return await _entry_to_response(entry, db)
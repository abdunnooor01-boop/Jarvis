"""Knowledge Feed API — endpoints for feed sources, entries, and crawling."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.auth import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.knowledge import (
    CrawlResponse,
    CrawlResult,
    DigestEntry,
    DigestResponse,
    DiscoveredTool,
    DiscoveryResult,
    FeedSourceCreate,
    FeedSourceListResponse,
    FeedSourceResponse,
    FeedSourceUpdate,
    KnowledgeEntryListResponse,
    KnowledgeEntryResponse,
)
from app.services.feed_crawler import FeedCrawler
from app.services.knowledge_store import KnowledgeStore
from app.services.tool_discovery import ToolDiscovery

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
_crawler: FeedCrawler | None = None
_store: KnowledgeStore | None = None
_discovery: ToolDiscovery | None = None


def _get_crawler() -> FeedCrawler:
    """Get or create the FeedCrawler singleton."""
    global _crawler
    if _crawler is None:
        _crawler = FeedCrawler()
    return _crawler


def _get_store() -> KnowledgeStore:
    """Get or create the KnowledgeStore singleton."""
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


def _get_discovery() -> ToolDiscovery:
    """Get or create the ToolDiscovery singleton."""
    global _discovery
    if _discovery is None:
        _discovery = ToolDiscovery()
    return _discovery


# ---------------------------------------------------------------------------
# Feed Sources
# ---------------------------------------------------------------------------


@router.get("/sources", response_model=FeedSourceListResponse)
async def list_sources(
    active_only: bool = Query(True, description="Only show active sources"),
    current_user: User = Depends(get_current_user),
) -> FeedSourceListResponse:
    """List all feed sources."""
    store = _get_store()
    sources = await store.list_sources(active_only=active_only)
    return FeedSourceListResponse(
        items=[FeedSourceResponse.model_validate(s) for s in sources],
        total=len(sources),
    )


@router.post("/sources", response_model=FeedSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    source: FeedSourceCreate,
    current_user: User = Depends(get_current_user),
) -> FeedSourceResponse:
    """Create a new feed source."""
    store = _get_store()
    created = await store.create_source(source.model_dump())
    return FeedSourceResponse.model_validate(created)


@router.get("/sources/{source_id}", response_model=FeedSourceResponse)
async def get_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> FeedSourceResponse:
    """Get details of a specific feed source."""
    store = _get_store()
    source = await store.get_source(str(source_id))
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return FeedSourceResponse.model_validate(source)


@router.patch("/sources/{source_id}", response_model=FeedSourceResponse)
async def update_source(
    source_id: uuid.UUID,
    update: FeedSourceUpdate,
    current_user: User = Depends(get_current_user),
) -> FeedSourceResponse:
    """Update a feed source."""
    store = _get_store()
    data = {k: v for k, v in update.model_dump().items() if v is not None}
    source = await store.update_source(str(source_id), data)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return FeedSourceResponse.model_validate(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a feed source and its entries."""
    store = _get_store()
    success = await store.delete_source(str(source_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Crawling
# ---------------------------------------------------------------------------


@router.post("/crawl", response_model=CrawlResponse)
async def crawl_all(
    current_user: User = Depends(get_current_user),
) -> CrawlResponse:
    """Crawl all active feed sources."""
    crawler = _get_crawler()
    await crawler.ensure_default_sources()
    results = await crawler.crawl_all()

    total_found = sum(r["entries_found"] for r in results)
    total_stored = sum(r["entries_stored"] for r in results)

    return CrawlResponse(
        results=[CrawlResult(**r) for r in results],
        total_entries_found=total_found,
        total_entries_stored=total_stored,
    )


@router.post("/crawl/{source_id}", response_model=CrawlResult)
async def crawl_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> CrawlResult:
    """Crawl a specific feed source."""
    crawler = _get_crawler()
    result = await crawler.crawl_source(str(source_id))
    return CrawlResult(**result)


# ---------------------------------------------------------------------------
# Knowledge Entries
# ---------------------------------------------------------------------------


@router.get("/entries", response_model=KnowledgeEntryListResponse)
async def list_entries(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    source_id: uuid.UUID | None = Query(None, description="Filter by source ID"),
    source_type: str | None = Query(None, description="Filter by source type"),
    topic: str | None = Query(None, description="Filter by topic"),
    search: str | None = Query(None, description="Search in title/summary/content"),
    unread_only: bool = Query(False, description="Only show unread entries"),
    current_user: User = Depends(get_current_user),
) -> KnowledgeEntryListResponse:
    """List knowledge entries with filtering and pagination."""
    store = _get_store()
    result = await store.list_entries(
        page=page,
        page_size=page_size,
        source_id=str(source_id) if source_id else None,
        source_type=source_type,
        topic=topic,
        search=search,
        unread_only=unread_only,
    )
    return KnowledgeEntryListResponse(
        items=[KnowledgeEntryResponse.model_validate(e) for e in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.get("/entries/{entry_id}", response_model=KnowledgeEntryResponse)
async def get_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> KnowledgeEntryResponse:
    """Get a specific knowledge entry."""
    store = _get_store()
    entry = await store.get_entry(str(entry_id))
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )
    return KnowledgeEntryResponse.model_validate(entry)


@router.post("/entries/{entry_id}/read", response_model=dict[str, bool])
async def mark_entry_read(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Mark a knowledge entry as read."""
    store = _get_store()
    success = await store.mark_read(str(entry_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )
    return {"success": True}


@router.post("/entries/read-all", response_model=dict[str, int])
async def mark_all_read(
    source_id: uuid.UUID | None = Query(None, description="Source ID to mark all read"),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Mark all entries as read."""
    store = _get_store()
    count = await store.mark_all_read(
        source_id=str(source_id) if source_id else None
    )
    return {"marked_read": count}


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a knowledge entry."""
    store = _get_store()
    success = await store.delete_entry(str(entry_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    hours_back: int = Query(168, ge=1, le=720, description="Hours back to include"),
    max_entries: int = Query(50, ge=1, le=200, description="Max entries in digest"),
    current_user: User = Depends(get_current_user),
) -> DigestResponse:
    """Generate a knowledge digest of recent entries."""
    crawler = _get_crawler()
    digest = await crawler.generate_digest(
        hours_back=hours_back,
        max_entries=max_entries,
    )
    return DigestResponse(
        generated_at=digest["generated_at"],
        total_entries=digest["total_entries"],
        entries=[DigestEntry(**e) for e in digest["entries"]],
    )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get knowledge base statistics."""
    store = _get_store()
    return await store.get_stats()


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Get the count of unread knowledge entries."""
    store = _get_store()
    count = await store.get_unread_count()
    return {"unread_count": count}


# ---------------------------------------------------------------------------
# Tool Discovery
# ---------------------------------------------------------------------------


@router.post("/discover", response_model=DiscoveryResult)
async def discover_tools(
    hours_back: int = Query(168, ge=1, le=720, description="Hours back to scan"),
    min_confidence: str = Query("low", pattern=r"^(high|medium|low)$"),
    current_user: User = Depends(get_current_user),
) -> DiscoveryResult:
    """Scan recent knowledge entries for discoverable tools."""
    discovery = _get_discovery()
    result = await discovery.scan_entries(
        hours_back=hours_back,
        min_confidence=min_confidence,
    )
    return DiscoveryResult(
        entries_scanned=result["entries_scanned"],
        tools_found=[DiscoveredTool(**t) for t in result["tools_found"]],
        scan_time_seconds=result["scan_time_seconds"],
    )


@router.post("/discover/{entry_id}/flag")
async def flag_tool_for_review(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Flag a discovered tool (from a knowledge entry) for human review."""
    discovery = _get_discovery()
    store = _get_store()
    entry = await store.get_entry(str(entry_id))
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    tool_info = await discovery._analyze_entry(entry)  # noqa: SLF001
    if tool_info is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This entry does not appear to describe a tool",
        )

    result = await discovery.flag_for_review(tool_info)
    return result

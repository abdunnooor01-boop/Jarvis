"""KnowledgeStore service — manages knowledge entries with semantic search."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.knowledge_entry import FeedSource, KnowledgeEntry

logger = get_logger(__name__)


class KnowledgeStore:
    """Manages knowledge entries with CRUD, search, and query operations.

    Builds on the model layer and is used by the API and scheduler.
    """

    # ------------------------------------------------------------------
    # Entry CRUD
    # ------------------------------------------------------------------

    async def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Get a single knowledge entry by ID."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
            )
            return result.scalar_one_or_none()

    async def list_entries(
        self,
        page: int = 1,
        page_size: int = 20,
        source_id: str | None = None,
        source_type: str | None = None,
        topic: str | None = None,
        search: str | None = None,
        unread_only: bool = False,
    ) -> dict[str, Any]:
        """List knowledge entries with filtering and pagination."""
        async with async_session_factory() as db:
            query = select(KnowledgeEntry)
            count_query = select(func.count(KnowledgeEntry.id))

            if source_id:
                query = query.where(KnowledgeEntry.source_id == source_id)
                count_query = count_query.where(KnowledgeEntry.source_id == source_id)

            if source_type:
                # Join with FeedSource to filter by type
                query = query.join(
                    FeedSource,
                    KnowledgeEntry.source_id == FeedSource.id,
                ).where(FeedSource.source_type == source_type)
                count_query = count_query.select_from(KnowledgeEntry).join(
                    FeedSource,
                    KnowledgeEntry.source_id == FeedSource.id,
                ).where(FeedSource.source_type == source_type)

            if topic:
                # Filter by topic (JSON array contains)
                query = query.where(KnowledgeEntry.topics.contains([topic]))
                count_query = count_query.where(KnowledgeEntry.topics.contains([topic]))

            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        KnowledgeEntry.title.ilike(search_term),
                        KnowledgeEntry.summary.ilike(search_term),
                        KnowledgeEntry.content.ilike(search_term),
                    )
                )
                count_query = count_query.where(
                    or_(
                        KnowledgeEntry.title.ilike(search_term),
                        KnowledgeEntry.summary.ilike(search_term),
                        KnowledgeEntry.content.ilike(search_term),
                    )
                )

            if unread_only:
                query = query.where(not KnowledgeEntry.is_read)
                count_query = count_query.where(not KnowledgeEntry.is_read)

            # Get total count
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            # Get paginated results
            offset = (page - 1) * page_size
            result = await db.execute(
                query.order_by(KnowledgeEntry.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            entries = result.scalars().all()

            pages = max(1, (total + page_size - 1) // page_size)

            return {
                "items": entries,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }

    async def mark_read(self, entry_id: str) -> bool:
        """Mark a knowledge entry as read."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return False
            entry.is_read = True
            await db.commit()
            return True

    async def mark_all_read(self, source_id: str | None = None) -> int:
        """Mark all entries as read, optionally filtered by source."""
        async with async_session_factory() as db:
            query = select(KnowledgeEntry).where(not KnowledgeEntry.is_read)
            if source_id:
                query = query.where(KnowledgeEntry.source_id == source_id)

            result = await db.execute(query)
            entries = result.scalars().all()

            for entry in entries:
                entry.is_read = True

            await db.commit()
            return len(entries)

    async def delete_entry(self, entry_id: str) -> bool:
        """Delete a knowledge entry."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return False
            await db.delete(entry)
            await db.commit()
            return True

    async def get_unread_count(self) -> int:
        """Get the count of unread entries."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(func.count(KnowledgeEntry.id)).where(
                    not KnowledgeEntry.is_read
                )
            )
            return result.scalar() or 0

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    async def list_sources(
        self, active_only: bool = True
    ) -> list[FeedSource]:
        """List all feed sources."""
        async with async_session_factory() as db:
            query = select(FeedSource)
            if active_only:
                query = query.where(FeedSource.is_active)
            query = query.order_by(FeedSource.name)
            result = await db.execute(query)
            return list(result.scalars().all())

    async def get_source(self, source_id: str) -> FeedSource | None:
        """Get a single feed source by ID."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FeedSource).where(FeedSource.id == source_id)
            )
            return result.scalar_one_or_none()

    async def create_source(self, data: dict[str, Any]) -> FeedSource:
        """Create a new feed source."""
        async with async_session_factory() as db:
            source = FeedSource(
                id=uuid.uuid4(),
                name=data["name"],
                source_type=data["source_type"],
                url=data.get("url"),
                config=data.get("config"),
                fetch_interval_minutes=data.get("fetch_interval_minutes", 60),
                is_active=True,
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            return source

    async def update_source(
        self, source_id: str, data: dict[str, Any]
    ) -> FeedSource | None:
        """Update an existing feed source."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FeedSource).where(FeedSource.id == source_id)
            )
            source = result.scalar_one_or_none()
            if source is None:
                return None

            for key, value in data.items():
                if hasattr(source, key) and value is not None:
                    setattr(source, key, value)

            await db.commit()
            await db.refresh(source)
            return source

    async def delete_source(self, source_id: str) -> bool:
        """Delete a feed source and its entries."""
        async with async_session_factory() as db:
            # Delete associated entries
            await db.execute(
                KnowledgeEntry.__table__.delete().where(
                    KnowledgeEntry.source_id == source_id
                )
            )
            # Delete the source
            result = await db.execute(
                select(FeedSource).where(FeedSource.id == source_id)
            )
            source = result.scalar_one_or_none()
            if source is None:
                return False
            await db.delete(source)
            await db.commit()
            return True

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        async with async_session_factory() as db:
            total_entries = await db.scalar(
                select(func.count(KnowledgeEntry.id))
            ) or 0
            unread = await db.scalar(
                select(func.count(KnowledgeEntry.id)).where(
                    not KnowledgeEntry.is_read
                )
            ) or 0
            source_count = await db.scalar(
                select(func.count(FeedSource.id)).where(
                    FeedSource.is_active
                )
            ) or 0

            # Get entries per source
            per_source = await db.execute(
                select(
                    KnowledgeEntry.source_name,
                    func.count(KnowledgeEntry.id).label("count"),
                )
                .group_by(KnowledgeEntry.source_name)
                .order_by(func.count(KnowledgeEntry.id).desc())
            )
            entries_by_source = [
                {"source": row[0], "count": row[1]}
                for row in per_source.fetchall()
            ]

            return {
                "total_entries": total_entries,
                "unread_entries": unread,
                "active_sources": source_count,
                "entries_by_source": entries_by_source,
            }

"""Memory service for vector-based long-term storage and retrieval."""

from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.memory import MemoryEntry

logger = get_logger(__name__)

# Default embedding dimension for OpenAI text-embedding-3-small
EMBEDDING_DIM = 1536


def _is_sqlite(db: AsyncSession) -> bool:
    """Detect if the database backend is SQLite."""
    return bool(db.bind and "sqlite" in str(db.bind.url))


class MemoryService:
    """Service for managing long-term memory with vector search.

    Handles embedding generation, storage, semantic search, and context
    retrieval. Supports both PostgreSQL+pgvector and SQLite fallback.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._openai_client: Any = None

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    async def _get_openai_client(self) -> Any:
        """Lazy-init the OpenAI client."""
        if self._openai_client is None:
            from openai import AsyncOpenAI

            from app.config import settings

            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text using OpenAI.

        Falls back to a zero-vector if no API key is configured (for tests).
        """
        from app.config import settings

        if not settings.openai_api_key or settings.openai_api_key == "test-mock-key":
            # Return a zero vector for testing or when no API key is set
            return [0.0] * EMBEDDING_DIM

        client = await self._get_openai_client()
        try:
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return [0.0] * EMBEDDING_DIM

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    async def store_memory(
        self,
        user_id: Any,
        type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Store a new memory entry with an embedding."""
        embedding = await self.generate_embedding(content)

        entry = MemoryEntry(
            user_id=user_id,
            type=type,
            content=content,
            embedding=json.dumps(embedding),
            metadata_=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def search_memories(
        self,
        user_id: Any,
        query: str,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search memories using semantic (or fallback) search.

        In PostgreSQL+pgvector, performs cosine distance search.
        In SQLite, falls back to basic keyword matching.
        """
        if _is_sqlite(self.db):
            return await self._search_sqlite_fallback(user_id, query, limit)

        return await self._search_pgvector(user_id, query, limit, threshold)

    async def _search_pgvector(
        self,
        user_id: Any,
        query: str,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Perform semantic search using pgvector cosine distance."""
        query_embedding = await self.generate_embedding(query)

        # Cosine distance: 1 - cosine_similarity
        # We use <= threshold since cosine_distance ranges 0-2, and
        # threshold of 0.7 corresponds to ~0.65 cosine similarity
        distance_threshold = 1.0 - threshold

        stmt = (
            select(
                MemoryEntry,
                text("1 - (embedding <=> :query_vec) AS score"),
            )
            .where(
                and_(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.deleted_at.is_(None),
                    text("embedding <=> :query_vec2 <= :thresh"),
                ),
            )
            .params(
                query_vec=json.dumps(query_embedding),
                query_vec2=json.dumps(query_embedding),
                thresh=distance_threshold,
            )
            .order_by(text("score DESC"))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "memory": row.MemoryEntry,
                "score": float(row.score),
            }
            for row in rows
        ]

    async def _search_sqlite_fallback(
        self,
        user_id: Any,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Basic keyword fallback search for SQLite environments."""
        keywords = query.lower().split()

        # Build OR conditions for each keyword matching content
        conditions = [
            MemoryEntry.content.ilike(f"%{kw}%") for kw in keywords
        ]

        stmt = (
            select(MemoryEntry)
            .where(
                and_(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.deleted_at.is_(None),
                    or_(*conditions),
                ),
            )
            .order_by(MemoryEntry.updated_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        # Simple scoring: count keyword matches / total keywords
        results = []
        for entry in entries:
            content_lower = entry.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            score = matches / len(keywords) if keywords else 0.0
            results.append({"memory": entry, "score": score})

        # Sort by score desc
        results.sort(key=lambda r: r["score"], reverse=True)

        return results

    async def get_relevant_context(
        self,
        user_id: Any,
        query: str,
        max_tokens: int = 2000,
    ) -> str:
        """Search memories and format as a context string for the LLM."""
        results = await self.search_memories(user_id, query)

        if not results:
            return ""

        context_parts: list[str] = []
        char_limit = max_tokens * 4  # Approximate token-to-char ratio

        for result in results:
            memory = result["memory"]
            entry_text = f"[{memory.type}] {memory.content} (relevance: {result['score']:.2f})"
            if sum(len(p) for p in context_parts) + len(entry_text) > char_limit:
                break
            context_parts.append(entry_text)

        if not context_parts:
            return ""

        return "Relevant context from past conversations:\n" + "\n".join(context_parts)

    # ------------------------------------------------------------------
    # Conversation Summarization
    # ------------------------------------------------------------------

    async def summarize_conversation(self, conversation_id: Any) -> MemoryEntry | None:
        """Summarize a conversation and store as a memory entry.

        Uses the LLM to generate a concise summary, or creates a basic
        text-based summary if no LLM is available.
        """
        from app.models.conversation import Conversation
        from app.models.message import Message

        # Get the conversation
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id),
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            logger.warning("Conversation not found for summarization", id=str(conversation_id))
            return None

        # Get all messages
        msg_result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.created_at.asc()),
        )
        messages = msg_result.scalars().all()

        if not messages:
            return None

        # Build a text summary from message content
        text_content = "\n".join(
            f"{m.role}: {m.content[:200]}" for m in messages
        )

        # Try to use LLM for summarization
        summary: str

        try:
            from app.services.llm import get_llm_service

            llm = get_llm_service()
            response = await llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the following conversation concisely in 2-3 sentences. "
                        "Focus on key facts, decisions, and user preferences mentioned.",
                    },
                    {"role": "user", "content": text_content},
                ],
            )
            summary = response.get("content", "")
            if not summary or len(summary) < 10:
                summary = self._build_basic_summary(conversation, messages)
        except Exception:
            logger.warning("LLM summarization failed, using basic summary")
            summary = self._build_basic_summary(conversation, messages)

        # Store as a memory entry
        metadata = {
            "conversation_id": str(conversation_id),
            "conversation_title": conversation.title,
            "message_count": len(messages),
        }

        return await self.store_memory(
            user_id=conversation.user_id,
            type="conversation_summary",
            content=summary,
            metadata=metadata,
        )

    def _build_basic_summary(
        self,
        conversation: Any,
        messages: list[Any],
    ) -> str:
        """Build a basic text summary without using an LLM."""
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]

        parts = [f"Conversation: {conversation.title}"]
        if user_messages:
            parts.append(f"User asked {len(user_messages)} questions")
        if assistant_messages:
            parts.append(f"Assistant provided {len(assistant_messages)} responses")

        # Include first user message as context
        if user_messages:
            first = user_messages[0].content[:150]
            parts.append(f"Started with: {first}")

        return ". ".join(parts)

    # ------------------------------------------------------------------
    # User Preferences
    # ------------------------------------------------------------------

    async def store_user_preference(self, user_id: Any, key: str, value: str) -> MemoryEntry:
        """Store a user preference as a memory entry.

        If a preference with the same key already exists, it is overwritten
        (soft-deleted + new entry created).
        """
        # Find existing preference with same key in metadata
        existing = await self.db.execute(
            select(MemoryEntry).where(
                and_(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.type == "preference",
                    MemoryEntry.deleted_at.is_(None),
                    MemoryEntry.metadata_["key"].as_string() == key,
                ),
            ),
        )
        old = existing.scalar_one_or_none()

        if old is not None:
            # Soft-delete the old preference
            old.deleted_at = func.now()

        return await self.store_memory(
            user_id=user_id,
            type="preference",
            content=value,
            metadata={"key": key},
        )

    async def get_user_preferences(self, user_id: Any) -> dict[str, str]:
        """Retrieve all user preferences as a key-value dict."""
        result = await self.db.execute(
            select(MemoryEntry).where(
                and_(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.type == "preference",
                    MemoryEntry.deleted_at.is_(None),
                ),
            ).order_by(MemoryEntry.updated_at.desc()),
        )
        entries = result.scalars().all()

        preferences: dict[str, str] = {}
        for entry in entries:
            key = (entry.metadata_ or {}).get("key")
            if key:
                preferences[key] = entry.content

        return preferences

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    async def delete_memory(self, memory_id: Any) -> bool:
        """Soft-delete a memory entry by ID."""
        result = await self.db.execute(
            select(MemoryEntry).where(
                and_(
                    MemoryEntry.id == memory_id,
                    MemoryEntry.deleted_at.is_(None),
                ),
            ),
        )
        entry = result.scalar_one_or_none()

        if entry is None:
            return False

        entry.deleted_at = func.now()
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    async def list_memories(
        self,
        user_id: Any,
        type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MemoryEntry], int]:
        """List memories with pagination and optional type filter."""
        conditions = [
            MemoryEntry.user_id == user_id,
            MemoryEntry.deleted_at.is_(None),
        ]

        if type is not None:
            conditions.append(MemoryEntry.type == type)

        # Count total
        count_stmt = select(func.count()).select_from(MemoryEntry).where(and_(*conditions))
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        stmt = (
            select(MemoryEntry)
            .where(and_(*conditions))
            .order_by(MemoryEntry.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())

        return entries, total


# Singleton per-session helper
def get_memory_service(db: AsyncSession) -> MemoryService:
    """Get a MemoryService instance bound to the given DB session."""
    return MemoryService(db)
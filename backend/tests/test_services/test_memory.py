"""Tests for memory service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryEntry
from app.services.memory import MemoryService


@pytest_asyncio.fixture
async def memory_service(db_session: AsyncSession) -> MemoryService:
    """Create a MemoryService bound to the test DB session."""
    return MemoryService(db_session)


@pytest.mark.asyncio
async def test_generate_embedding_no_key(memory_service: MemoryService) -> None:
    """Test embedding generation returns zero vector when no API key is set."""
    with patch("app.config.settings.openai_api_key", "test-mock-key"):
        embedding = await memory_service.generate_embedding("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(v == 0.0 for v in embedding)


@pytest.mark.asyncio
async def test_store_memory(memory_service: MemoryService, db_session: AsyncSession) -> None:
    """Test storing a memory entry."""
    import uuid

    user_id = uuid.uuid4()
    memory = await memory_service.store_memory(
        user_id=user_id,
        type="fact",
        content="The user likes Python programming",
        metadata={"source": "chat"},
    )

    assert memory.id is not None
    assert memory.type == "fact"
    assert memory.content == "The user likes Python programming"
    assert memory.metadata_ == {"source": "chat"}
    assert memory.deleted_at is None


@pytest.mark.asyncio
async def test_store_memory_preference_type(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test storing a preference type memory."""
    import uuid

    user_id = uuid.uuid4()
    memory = await memory_service.store_memory(
        user_id=user_id,
        type="preference",
        content="dark_mode",
        metadata={"key": "theme"},
    )

    assert memory.type == "preference"
    assert memory.metadata_ == {"key": "theme"}


@pytest.mark.asyncio
async def test_search_memories_sqlite_fallback(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test searching memories with SQLite fallback (keyword matching)."""
    import uuid

    user_id = uuid.uuid4()

    # Store multiple memories
    await memory_service.store_memory(
        user_id=user_id,
        type="fact",
        content="The user enjoys hiking in the mountains",
    )
    await memory_service.store_memory(
        user_id=user_id,
        type="fact",
        content="The user prefers coffee over tea",
    )
    await memory_service.store_memory(
        user_id=user_id,
        type="conversation_summary",
        content="Discussed hiking trails in Yosemite",
    )

    # Search for hiking-related content
    results = await memory_service.search_memories(
        user_id=user_id,
        query="hiking",
        limit=5,
    )

    assert len(results) >= 1
    # Should find the hiking-related memories
    contents = [r["memory"].content for r in results]
    assert any("hiking" in c.lower() for c in contents)


@pytest.mark.asyncio
async def test_search_memories_empty_results(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test search returns empty list when no matches found."""
    import uuid

    user_id = uuid.uuid4()

    results = await memory_service.search_memories(
        user_id=user_id,
        query="nonexistent content",
        limit=5,
    )

    assert results == []


@pytest.mark.asyncio
async def test_get_relevant_context(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test getting relevant context as formatted string."""
    import uuid

    user_id = uuid.uuid4()

    await memory_service.store_memory(
        user_id=user_id,
        type="fact",
        content="User works as a software engineer",
    )

    context = await memory_service.get_relevant_context(
        user_id=user_id,
        query="software engineer work",
    )

    assert isinstance(context, str)
    assert "software engineer" in context.lower()
    assert "Relevant context from past conversations" in context


@pytest.mark.asyncio
async def test_get_relevant_context_no_matches(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test context returns empty string when no matches."""
    import uuid

    user_id = uuid.uuid4()

    context = await memory_service.get_relevant_context(
        user_id=user_id,
        query="anything",
    )

    assert context == ""


@pytest.mark.asyncio
async def test_summarize_conversation_empty(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test summarizing a non-existent conversation returns None."""
    import uuid

    result = await memory_service.summarize_conversation(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_store_and_get_preferences(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test storing and retrieving user preferences."""
    import uuid

    user_id = uuid.uuid4()

    # Store preferences
    await memory_service.store_user_preference(user_id, "theme", "dark")
    await memory_service.store_user_preference(user_id, "language", "Python")

    # Retrieve preferences
    preferences = await memory_service.get_user_preferences(user_id)

    assert preferences["theme"] == "dark"
    assert preferences["language"] == "Python"


@pytest.mark.asyncio
async def test_update_preference_overwrites(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test updating a preference overwrites the old one."""
    import uuid

    user_id = uuid.uuid4()

    await memory_service.store_user_preference(user_id, "theme", "dark")
    await memory_service.store_user_preference(user_id, "theme", "light")

    preferences = await memory_service.get_user_preferences(user_id)
    assert preferences["theme"] == "light"


@pytest.mark.asyncio
async def test_delete_memory(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test soft-deleting a memory entry."""
    import uuid

    user_id = uuid.uuid4()

    memory = await memory_service.store_memory(
        user_id=user_id,
        type="fact",
        content="Test memory to delete",
    )

    # Verify it exists
    results = await memory_service.search_memories(
        user_id=user_id,
        query="delete",
        limit=5,
    )
    assert len(results) == 1

    # Delete it
    success = await memory_service.delete_memory(memory.id)
    assert success is True

    # Verify it's gone
    results = await memory_service.search_memories(
        user_id=user_id,
        query="delete",
        limit=5,
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_memory(memory_service: MemoryService) -> None:
    """Test deleting a non-existent memory returns False."""
    import uuid

    success = await memory_service.delete_memory(uuid.uuid4())
    assert success is False


@pytest.mark.asyncio
async def test_list_memories(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test listing memories with pagination."""
    import uuid

    user_id = uuid.uuid4()

    for i in range(5):
        await memory_service.store_memory(
            user_id=user_id,
            type="fact",
            content=f"Test fact number {i}",
        )

    entries, total = await memory_service.list_memories(
        user_id=user_id,
        page=1,
        page_size=3,
    )

    assert total == 5
    assert len(entries) == 3


@pytest.mark.asyncio
async def test_list_memories_filter_by_type(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test listing memories filtered by type."""
    import uuid

    user_id = uuid.uuid4()

    await memory_service.store_memory(
        user_id=user_id,
        type="fact",
        content="A fact",
    )
    await memory_service.store_memory(
        user_id=user_id,
        type="preference",
        content="A preference",
    )

    entries, total = await memory_service.list_memories(
        user_id=user_id,
        type="fact",
    )

    assert total == 1
    assert len(entries) == 1
    assert entries[0].type == "fact"


@pytest.mark.asyncio
async def test_list_memories_user_isolation(
    memory_service: MemoryService,
    db_session: AsyncSession,
) -> None:
    """Test that memories are isolated per user."""
    import uuid

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    await memory_service.store_memory(
        user_id=user_a,
        type="fact",
        content="User A's fact",
    )
    await memory_service.store_memory(
        user_id=user_b,
        type="fact",
        content="User B's fact",
    )

    entries_a, total_a = await memory_service.list_memories(user_id=user_a)
    entries_b, total_b = await memory_service.list_memories(user_id=user_b)

    assert total_a == 1
    assert total_b == 1
    assert entries_a[0].content == "User A's fact"
    assert entries_b[0].content == "User B's fact"
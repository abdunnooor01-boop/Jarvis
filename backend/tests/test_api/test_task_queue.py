"""Tests for the offline task queue — remote task submission, polling, and listing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import uuid
import pytest

from app.models.task_queue import TaskQueueItem


@pytest.mark.asyncio
async def test_task_queue_item_model() -> None:
    """Test that TaskQueueItem model has the expected fields."""
    assert hasattr(TaskQueueItem, "id")
    assert hasattr(TaskQueueItem, "user_id")
    assert hasattr(TaskQueueItem, "task_type")
    assert hasattr(TaskQueueItem, "params")
    assert hasattr(TaskQueueItem, "status")
    assert hasattr(TaskQueueItem, "result")
    assert hasattr(TaskQueueItem, "error_message")
    assert hasattr(TaskQueueItem, "progress")
    assert hasattr(TaskQueueItem, "source_device")
    assert hasattr(TaskQueueItem, "queued_at")
    assert hasattr(TaskQueueItem, "started_at")
    assert hasattr(TaskQueueItem, "completed_at")


@pytest.mark.asyncio
async def test_engine_init() -> None:
    """Test that the multitasking engine initializes correctly."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=3)
    assert engine.max_workers == 3
    assert engine.active_count == 0
    assert engine.active_task_ids == []


@pytest.mark.asyncio
async def test_engine_stats() -> None:
    """Test that get_stats returns correct structure."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=5)
    stats = engine.get_stats()
    assert stats["max_workers"] == 5
    assert stats["active_tasks"] == 0
    assert stats["available_slots"] == 5
    assert stats["task_ids"] == []


@pytest.mark.asyncio
async def test_enqueue_task() -> None:
    """Test enqueuing a task."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=5)

    mock_item = MagicMock(spec=TaskQueueItem)
    mock_item.id = "test-task-id"
    mock_item.task_type = "chat"
    mock_item.user_id = "user-1"
    mock_item.params = {"query": "Hello"}
    mock_item.metadata_ = {}
    mock_item.status = "queued"
    mock_item.queued_at = MagicMock()
    mock_item.queued_at.isoformat.return_value = "2026-01-01T00:00:00"

    mock_db = AsyncMock()

    result = await engine.enqueue(mock_item, mock_db)
    assert result.id == "test-task-id"
    assert engine.active_count == 1

    # Clean up
    engine._active_tasks.clear()


@pytest.mark.asyncio
async def test_get_stats_after_enqueue() -> None:
    """Test stats reflect active tasks."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=2)

    mock_task = AsyncMock()
    mock_task.done.return_value = False
    engine._active_tasks["task-1"] = mock_task
    engine._active_tasks["task-2"] = mock_task

    stats = engine.get_stats()
    assert stats["active_tasks"] == 2
    assert stats["available_slots"] == 0

    engine._active_tasks.clear()


@pytest.mark.asyncio
async def test_task_queue_api_router() -> None:
    """Test that the task queue API router has the expected routes."""
    from app.api.task_queue import router

    routes = [(r.path, list(r.methods)) for r in router.routes]
    paths = [r[0] for r in routes]

    assert "/api/v1/tasks" in paths  # POST /api/v1/tasks (submit)
    assert "/api/v1/tasks/{task_id}" in paths  # GET /api/v1/tasks/{id}
    assert "/api/v1/tasks/{task_id}/cancel" in paths  # POST /api/v1/tasks/{id}/cancel


@pytest.mark.asyncio
async def test_task_submit_schema() -> None:
    """Test that the TaskSubmitRequest schema validates correctly."""
    from app.api.task_queue import TaskSubmitRequest

    # Valid request
    req = TaskSubmitRequest(
        task_type="chat",
        params={"query": "Hello"},
        source_device="ios",
    )
    assert req.task_type == "chat"
    assert req.params == {"query": "Hello"}
    assert req.source_device == "ios"
    assert req.max_retries == 3


@pytest.mark.asyncio
async def test_model_default_status(db_session) -> None:
    """Test that new TaskQueueItem defaults to 'queued' status.

    SQLAlchemy ``mapped_column(default=...)`` values are applied at flush
    time, so the object must be added and flushed before defaults appear.
    """
    item = TaskQueueItem(
        user_id=uuid.uuid4(),
        task_type="test",
        params={},
    )
    db_session.add(item)
    await db_session.flush()
    assert item.status == "queued"
    assert item.progress == 0
    assert item.retry_count == 0
    assert item.max_retries == 3
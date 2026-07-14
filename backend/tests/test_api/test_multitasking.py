"""Tests for the multitasking engine and task queue API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.task_plan import TaskPlan
from app.models.task_step import TaskStep


@pytest.mark.asyncio
async def test_multitasking_engine_init() -> None:
    """Test that the engine initializes with correct defaults."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=3)
    assert engine.max_workers == 3
    assert engine.active_plan_count == 0
    assert engine.active_plan_ids == []


@pytest.mark.asyncio
async def test_multitasking_engine_stats() -> None:
    """Test that get_stats returns correct structure."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=5)
    stats = engine.get_stats()
    assert stats["max_workers"] == 5
    assert stats["active_plans"] == 0
    assert stats["available_worker_slots"] == 5
    assert stats["plan_ids"] == []


@pytest.mark.asyncio
async def test_enqueue_and_cancel_plan() -> None:
    """Test enqueuing and cancelling a plan."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=5)

    # Create a mock plan
    mock_plan = MagicMock(spec=TaskPlan)
    mock_plan.id = "test-plan-id"
    mock_plan.goal = "Test goal"
    mock_plan.status = "pending"
    mock_plan.total_steps = 0
    mock_plan.completed_steps = 0
    mock_plan.failed_steps = 0
    mock_plan.max_retries = 2
    mock_plan.error_mode = "abort"
    mock_plan.steps = []

    mock_db = AsyncMock()

    # Enqueue
    plan = await engine.enqueue_plan(mock_plan, mock_db)
    assert plan.id == "test-plan-id"
    assert engine.active_plan_count == 1

    # Cancel
    success = await engine.cancel_plan("test-plan-id")
    assert success

    # Clean up
    engine._active_tasks.clear()


@pytest.mark.asyncio
async def test_cancel_all_plans() -> None:
    """Test cancelling all plans."""
    from app.services.multitasking import MultitaskingEngine

    engine = MultitaskingEngine(max_concurrent_workers=5)

    # Add a couple of mock tasks
    mock_task = AsyncMock()
    mock_task.done.return_value = False
    engine._active_tasks["plan-1"] = mock_task
    engine._active_tasks["plan-2"] = mock_task

    count = await engine.cancel_all()
    assert count == 2
    assert engine.active_plan_count == 0


@pytest.mark.asyncio
async def test_shared_types_exist() -> None:
    """Test that the shared task types file exists."""
    import os

    path = "/home/agent-backend-engineer/jarvis-repo/packages/shared/src/types/tasks.ts"
    assert os.path.exists(path), f"Shared types file not found at {path}"
    content = open(path).read()
    assert "TaskQueueItem" in content
    assert "TaskEnqueueResponse" in content
    assert "WorkerPoolStats" in content


@pytest.mark.asyncio
async def test_task_queue_api_router() -> None:
    """Test that the task queue API router exists with correct routes."""
    from app.api.task_queue import router

    routes = [(r.path, list(r.methods)) for r in router.routes]
    paths = [r[0] for r in routes]

    assert "" in paths  # GET /api/v1/tasks/queue (list)
    assert "/stats" in paths  # GET /api/v1/tasks/queue/stats
    assert "/{plan_id}" in paths  # GET /api/v1/tasks/queue/{id}
    assert "/{plan_id}/cancel" in paths  # POST /api/v1/tasks/queue/{id}/cancel
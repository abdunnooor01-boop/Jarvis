"""Multitasking engine — parallel task execution with Semaphore-based worker pool.

Processes tasks from the TaskQueueItem model using a configurable worker pool.
Designed for server-side execution of tasks submitted by mobile/desktop clients.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.task_queue import TaskQueueItem
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)


class MultitaskingEngine:
    """Manages async execution of tasks from the task queue.

    Uses an asyncio.Semaphore to limit concurrent executions.
    Designed for server-side remote task execution — tasks persist
    in the database and survive restarts.
    """

    def __init__(self, max_concurrent_workers: int = 5) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_workers)
        self._max_workers = max_concurrent_workers
        self._executor = ToolExecutor()
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    @property
    def active_task_ids(self) -> list[str]:
        return list(self._active_tasks.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(self, item: TaskQueueItem, db: AsyncSession) -> TaskQueueItem:
        """Enqueue a task for background execution.

        Persists the task in the database and starts execution.
        Returns immediately — execution happens in the background.
        """
        task_id_str = str(item.id)

        async def _run():
            async with self._semaphore:
                await self._execute(item)

        task = asyncio.create_task(_run(), name=f"task-{task_id_str}")
        self._active_tasks[task_id_str] = task

        logger.info(
            "Task enqueued",
            task_id=task_id_str,
            task_type=item.task_type,
            active_count=self.active_count,
        )
        return item

    async def get_status(self, task_id: str) -> dict[str, Any] | None:
        """Get the current status of a task."""
        async with async_session_factory() as db:
            item_id = uuid.UUID(str(task_id))
            result = await db.execute(
                select(TaskQueueItem).where(TaskQueueItem.id == item_id)
            )
            item = result.scalar_one_or_none()
            if item is None:
                return None
            return self._item_to_dict(item)

    async def list_tasks(
        self,
        user_id: str,
        status_filter: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List tasks for a user, with optional status filter."""
        async with async_session_factory() as db:
            query = select(TaskQueueItem).where(
                TaskQueueItem.user_id == user_id
            )

            if status_filter:
                query = query.where(TaskQueueItem.status == status_filter)

            query = query.order_by(TaskQueueItem.queued_at.desc()).limit(limit)
            result = await db.execute(query)
            items = result.scalars().all()
            return [self._item_to_dict(item) for item in items]

    async def cancel(self, task_id: str) -> bool:
        """Cancel a queued or running task."""
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            self._active_tasks.pop(task_id, None)

        async with async_session_factory() as db:
            item_id = uuid.UUID(str(task_id))
            result = await db.execute(
                select(TaskQueueItem).where(TaskQueueItem.id == item_id)
            )
            item = result.scalar_one_or_none()
            if item and item.status in ("queued", "running"):
                item.status = "cancelled"
                item.completed_at = datetime.now(UTC)
                await db.commit()
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get worker pool statistics."""
        return {
            "max_workers": self._max_workers,
            "active_tasks": self.active_count,
            "available_slots": max(0, self._max_workers - self.active_count),
            "task_ids": self.active_task_ids,
        }

    # ------------------------------------------------------------------
    # Internal: execution
    # ------------------------------------------------------------------

    async def _execute(self, item: TaskQueueItem) -> None:
        """Execute a single task and update its status."""
        task_id_str = str(item.id)

        async with async_session_factory() as db:
            # Refresh from DB
            result = await db.execute(
                select(TaskQueueItem).where(TaskQueueItem.id == item.id)
            )
            item = result.scalar_one_or_none()
            if item is None:
                return

            item.status = "running"
            item.started_at = datetime.now(UTC)
            await db.commit()

        logger.info(
            "Task execution started",
            task_id=task_id_str,
            task_type=item.task_type,
        )

        # Execute with retries
        for attempt in range(item.max_retries + 1):
            if attempt > 0:
                item.retry_count = attempt
                async with async_session_factory() as db:
                    await db.commit()

            try:
                result = await self._run_task(item.task_type, item.params or {})

                # Success
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(TaskQueueItem).where(TaskQueueItem.id == item.id)
                    )
                    item = result.scalar_one_or_none()
                    if item is None:
                        return

                    item.status = "completed"
                    item.result = json.dumps(result, default=str)
                    item.progress = 100
                    item.completed_at = datetime.now(UTC)
                    await db.commit()

                logger.info(
                    "Task completed",
                    task_id=task_id_str,
                    task_type=item.task_type,
                )
                self._active_tasks.pop(task_id_str, None)
                return

            except Exception as e:
                logger.warning(
                    "Task attempt failed",
                    task_id=task_id_str,
                    attempt=attempt,
                    error=str(e),
                )

                async with async_session_factory() as db:
                    result = await db.execute(
                        select(TaskQueueItem).where(TaskQueueItem.id == item.id)
                    )
                    item = result.scalar_one_or_none()
                    if item is None:
                        return

                    item.error_message = str(e)
                    item.progress = min(100, int((attempt + 1) / (item.max_retries + 1) * 100))
                    await db.commit()

                if attempt < item.max_retries:
                    await asyncio.sleep(1 * (attempt + 1))

        # All retries exhausted
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskQueueItem).where(TaskQueueItem.id == item.id)
            )
            item = result.scalar_one_or_none()
            if item is None:
                return

            item.status = "failed"
            item.completed_at = datetime.now(UTC)
            await db.commit()

        logger.error(
            "Task failed after all retries",
            task_id=task_id_str,
            task_type=item.task_type,
        )
        self._active_tasks.pop(task_id_str, None)

    async def _run_task(
        self,
        task_type: str,
        params: dict[str, Any],
    ) -> Any:
        """Route a task to the appropriate executor based on task type."""
        tool_map = {
            "chat": "chat",
            "browse": "browser_web",
            "search": "web_search",
            "test": "run_tests",
            "code": "run_code",
            "file": "file_ops",
            "freelance": "freelance_task",
            "memory": "memory_search",
            "knowledge": "knowledge_search",
        }

        tool_name = tool_map.get(task_type)
        if tool_name:
            result = await self._executor.execute(
                tool_name=tool_name,
                arguments=params,
            )
            return result

        # Fallback: return the params as the result
        return {"message": f"Task type '{task_type}' processed", "params": params}

    def _item_to_dict(self, item: TaskQueueItem) -> dict[str, Any]:
        """Convert a TaskQueueItem ORM object to a response dict."""
        return {
            "id": str(item.id),
            "user_id": str(item.user_id),
            "task_type": item.task_type,
            "params": item.params or {},
            "metadata": item.metadata_ or {},
            "status": item.status,
            "result": item.result,
            "error_message": item.error_message,
            "progress": item.progress,
            "retry_count": item.retry_count,
            "max_retries": item.max_retries,
            "source_device": item.source_device,
            "queued_at": item.queued_at.isoformat(),
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "updated_at": item.updated_at.isoformat(),
        }


# Singleton
_engine: MultitaskingEngine | None = None


def get_engine(max_workers: int = 5) -> MultitaskingEngine:
    global _engine
    if _engine is None:
        _engine = MultitaskingEngine(max_concurrent_workers=max_workers)
    return _engine
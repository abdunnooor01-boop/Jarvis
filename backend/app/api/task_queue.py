"""Task Queue API — remote task submission, polling, and listing for offline execution.

Mobile/desktop clients submit tasks to the queue, and the server-side
worker pool executes them. Results persist in the database so clients
can retrieve them after reconnecting.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.task_queue import TaskQueueItem
from app.models.user import User
from app.services.multitasking import get_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_task(
    body: TaskSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Submit a new task for server-side execution.

    The task is persisted in the database and queued for execution
    by the worker pool. Returns a task ID immediately.
    The client can poll GET /api/v1/tasks/{id} for status updates.
    """
    item = TaskQueueItem(
        user_id=current_user.id,
        task_type=body.task_type,
        params=body.params,
        metadata_=body.metadata,
        max_retries=body.max_retries or 3,
        source_device=body.source_device,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Enqueue for background execution
    engine = get_engine()
    await engine.enqueue(item, db)

    logger.info(
        "Task submitted",
        task_id=str(item.id),
        task_type=body.task_type,
        user_id=str(current_user.id),
    )

    return {
        "id": str(item.id),
        "task_type": item.task_type,
        "status": item.status,
        "queued_at": item.queued_at.isoformat(),
        "message": "Task has been queued for server-side execution",
    }


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the status and result of a task.

    Returns the full task details including status, progress,
    result (if completed), and error info (if failed).
    """
    engine = get_engine()
    status_data = await engine.get_status(task_id)

    if status_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if str(status_data["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task",
        )

    return status_data


@router.get("")
async def list_tasks(
    status: str | None = Query(None, description="Filter by status: queued, running, completed, failed, cancelled"),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List all tasks for the current user.

    Optionally filter by status. Returns most recent tasks first.
    """
    engine = get_engine()
    items = await engine.list_tasks(
        user_id=str(current_user.id),
        status_filter=status,
        limit=limit,
    )

    return {
        "items": items,
        "total": len(items),
    }


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a queued or running task."""
    engine = get_engine()
    success = await engine.cancel(task_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or already completed",
        )

    return {
        "id": task_id,
        "status": "cancelled",
        "message": "Task has been cancelled",
    }


# ------------------------------------------------------------------
# Schemas (inline to keep things simple)
# ------------------------------------------------------------------


from pydantic import BaseModel, Field


class TaskSubmitRequest(BaseModel):
    """Request to submit a new task for server-side execution."""

    task_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Task type: chat, browse, search, test, code, file, freelance, memory, knowledge",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Task parameters (varies by task type)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (source device, tags, etc.)",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries on failure",
    )
    source_device: str | None = Field(
        default=None,
        max_length=100,
        description="Device that submitted the task (ios, android, web, desktop)",
    )
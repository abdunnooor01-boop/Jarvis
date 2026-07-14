"""Task Queue API — enqueue, monitor, and manage parallel task execution."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.user import User
from app.schemas.task_plan import PlanGenerationRequest
from app.services.multitasking import get_multitasking_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tasks/queue", tags=["task-queue"])


@router.get("")
async def list_queue(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List all queued and running tasks."""
    engine = get_multitasking_engine()
    items = await engine.list_queue()
    return {
        "items": items,
        "total": len(items),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def enqueue_task(
    body: PlanGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Enqueue a new task from a goal for parallel execution.

    Generates a plan from the goal and adds it to the worker pool.
    Returns immediately with the plan ID — execution happens in the background.
    """
    engine = get_multitasking_engine()
    plans = await engine.enqueue_goals(
        goals=[body.goal],
        user_id=current_user.id,
        db=db,
    )

    if not plans:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate plan from goal",
        )

    plan = plans[0]
    stats = engine.get_stats()

    logger.info(
        "Task enqueued",
        plan_id=str(plan.id),
        active_plans=stats["active_plans"],
    )

    return {
        "plan_id": str(plan.id),
        "goal": plan.goal,
        "status": "queued",
        "total_steps": len(plan.steps),
        "message": "Task has been queued for execution",
        "worker_pool": stats,
    }


@router.get("/stats")
async def queue_stats(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get worker pool statistics."""
    engine = get_multitasking_engine()
    return engine.get_stats()


@router.get("/{plan_id}")
async def get_queue_item(
    plan_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the status and progress of a specific queued task."""
    engine = get_multitasking_engine()
    status = await engine.get_plan_status(plan_id)

    if status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    return status


@router.post("/{plan_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_queue_item(
    plan_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a queued or running task."""
    engine = get_multitasking_engine()
    success = await engine.cancel_plan(plan_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found or already completed",
        )

    return {
        "plan_id": plan_id,
        "status": "cancelled",
        "message": "Task has been cancelled",
    }
"""Task API routes — plan creation, execution, and lifecycle management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.task import TaskPlan, TaskStep
from app.models.user import User
from app.schemas.task import (
    ActionResponse,
    CreatePlanRequest,
    ExecutePlanResponse,
    TaskListResponse,
    TaskPlanResponse,
    TaskStepResponse,
)
from app.services.task_executor import TaskExecutionEngine
from app.services.task_planner import TaskPlanner

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# Singleton instances
_planner: TaskPlanner | None = None
_executor: TaskExecutionEngine | None = None


def _get_planner() -> TaskPlanner:
    """Get or create the TaskPlanner singleton."""
    global _planner
    if _planner is None:
        _planner = TaskPlanner()
    return _planner


def _get_executor() -> TaskExecutionEngine:
    """Get or create the TaskExecutionEngine singleton."""
    global _executor
    if _executor is None:
        _executor = TaskExecutionEngine()
    return _executor


def _plan_to_response(plan: TaskPlan) -> TaskPlanResponse:
    """Convert a TaskPlan ORM object to a response schema."""
    return TaskPlanResponse(
        id=plan.id,
        goal=plan.goal,
        title=plan.title,
        status=plan.status,
        error_mode=plan.error_mode,
        max_retries=plan.max_retries,
        total_steps=plan.total_steps,
        completed_steps=plan.completed_steps,
        failed_steps=plan.failed_steps,
        steps=[_step_to_response(s) for s in sorted(plan.steps, key=lambda s: s.step_order)],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        started_at=plan.started_at,
        completed_at=plan.completed_at,
    )


def _step_to_response(step: TaskStep) -> TaskStepResponse:
    """Convert a TaskStep ORM object to a response schema."""
    return TaskStepResponse(
        id=step.id,
        step_order=step.step_order,
        tool_name=step.tool_name,
        tool_params=step.tool_params,
        description=step.description,
        status=step.status,
        result=step.result,
        error=step.error,
        retry_count=step.retry_count,
        started_at=step.started_at,
        completed_at=step.completed_at,
    )


@router.post("/plan", response_model=TaskPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: CreatePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskPlanResponse:
    """Create a task plan by breaking down a goal into executable steps."""
    planner = _get_planner()

    # Generate plan steps via LLM
    steps_data = await planner.plan(body.goal)

    if not steps_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not generate a plan for this goal. Try being more specific.",
        )

    # Create the plan in DB
    plan = TaskPlan(
        user_id=current_user.id,
        goal=body.goal,
        title=body.goal[:100],
        status="pending",  # Needs user approval before execution
        error_mode=body.error_mode,
        max_retries=body.max_retries,
        total_steps=len(steps_data),
    )
    db.add(plan)
    await db.flush()

    # Create steps
    for i, step_data in enumerate(steps_data):
        step = TaskStep(
            plan_id=plan.id,
            step_order=i,
            tool_name=step_data.get("tool_name", ""),
            tool_params=step_data.get("tool_params", {}),
            description=step_data.get("description", ""),
        )
        db.add(step)

    await db.commit()
    await db.refresh(plan)

    logger.info(
        "Plan created",
        plan_id=str(plan.id),
        user_id=str(current_user.id),
        step_count=len(steps_data),
    )

    return _plan_to_response(plan)


@router.post("/{plan_id}/execute", response_model=ExecutePlanResponse)
async def execute_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutePlanResponse:
    """Start executing a plan (background task)."""
    result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    if plan.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plan is in '{plan.status}' state — can only execute pending plans",
        )

    # Auto-approve and start execution
    plan.status = "approved"
    await db.commit()

    executor = _get_executor()

    # Start execution in the background
    import asyncio

    asyncio.create_task(
        executor.execute_plan(
            plan_id=str(plan.id),
            user_id=str(current_user.id),
        )
    )

    logger.info("Plan execution started", plan_id=str(plan.id), user_id=str(current_user.id))

    return ExecutePlanResponse(
        plan_id=plan.id,
        status="running",
        message="Plan execution has started in the background",
    )


@router.get("/{plan_id}", response_model=TaskPlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskPlanResponse:
    """Get the status and details of a task plan."""
    result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    return _plan_to_response(plan)


@router.post("/{plan_id}/pause", response_model=ActionResponse)
async def pause_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionResponse:
    """Pause a running plan."""
    result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    executor = _get_executor()
    success = await executor.pause_plan(str(plan.id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan is not in a running state",
        )

    return ActionResponse(
        plan_id=plan.id,
        status="paused",
        message="Plan execution has been paused",
    )


@router.post("/{plan_id}/resume", response_model=ActionResponse)
async def resume_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionResponse:
    """Resume a paused plan."""
    result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    executor = _get_executor()
    success = await executor.resume_plan(str(plan.id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan is not in a paused state",
        )

    return ActionResponse(
        plan_id=plan.id,
        status="running",
        message="Plan execution has been resumed",
    )


@router.post("/{plan_id}/cancel", response_model=ActionResponse)
async def cancel_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionResponse:
    """Cancel a running or paused plan."""
    result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    executor = _get_executor()
    success = await executor.cancel_plan(str(plan.id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan is not in a running or paused state",
        )

    return ActionResponse(
        plan_id=plan.id,
        status="cancelled",
        message="Plan execution has been cancelled",
    )


@router.get("", response_model=TaskListResponse)
async def list_plans(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """List all task plans for the current user with pagination."""
    # Get total count
    count_result = await db.execute(
        select(func.count(TaskPlan.id)).where(TaskPlan.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    # Get paginated plans
    offset = (page - 1) * page_size
    result = await db.execute(
        select(TaskPlan)
        .where(TaskPlan.user_id == current_user.id)
        .order_by(TaskPlan.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    plans = result.scalars().all()

    return TaskListResponse(
        items=[_plan_to_response(p) for p in plans],
        total=total,
        page=page,
        page_size=page_size,
    )

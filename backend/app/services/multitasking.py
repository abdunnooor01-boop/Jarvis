"""Multitasking engine — parallel task execution with Semaphore-based worker pool.

Extends the existing TaskPlanner and TaskExecutionEngine to run multiple
plans concurrently using an asyncio.Semaphore-based worker pool.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.task_plan import TaskPlan
from app.models.task_step import TaskStep
from app.services.task_planner import TaskPlanner, get_task_planner
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)


class MultitaskingEngine:
    """Manages parallel execution of multiple task plans.

    Uses an asyncio.Semaphore to limit concurrent step execution
    and a worker pool to process steps from multiple plans in parallel.

    Each plan's steps run sequentially, but multiple plans can run
    concurrently, limited by the semaphore.
    """

    def __init__(
        self,
        max_concurrent_workers: int = 5,
        planner: TaskPlanner | None = None,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_workers)
        self._max_workers = max_concurrent_workers
        self._planner = planner or get_task_planner()
        self._executor = ToolExecutor()
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def active_plan_count(self) -> int:
        return len(self._active_tasks)

    @property
    def active_plan_ids(self) -> list[str]:
        return list(self._active_tasks.keys())

    async def enqueue_plan(
        self,
        plan: TaskPlan,
        db: AsyncSession,
    ) -> TaskPlan:
        """Enqueue a plan and start executing it in the background.

        The plan is executed via the semaphore-controlled worker pool.
        Returns immediately after starting the background task.
        """
        plan_id_str = str(plan.id)
        self._cancel_events[plan_id_str] = asyncio.Event()

        task = asyncio.create_task(
            self._execute_plan_with_semaphore(plan, db),
            name=f"plan-{plan_id_str}",
        )
        self._active_tasks[plan_id_str] = task

        logger.info(
            "Plan enqueued for execution",
            plan_id=plan_id_str,
            active_count=len(self._active_tasks),
        )
        return plan

    async def enqueue_goals(
        self,
        goals: list[str],
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> list[TaskPlan]:
        """Generate plans from goals and enqueue them all for execution."""
        plans: list[TaskPlan] = []
        for goal in goals:
            plan = await self._planner.generate_plan(goal, db, user_id)
            plans.append(plan)

        if not plans:
            return []

        logger.info(
            "Generated plans for parallel execution",
            plan_count=len(plans),
        )

        for plan in plans:
            await self.enqueue_plan(plan, db)

        return plans

    async def get_plan_status(self, plan_id: str) -> dict[str, Any] | None:
        """Get the current status of a queued/running plan."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                return None

            await db.refresh(plan, ["steps"])
            return {
                "id": str(plan.id),
                "goal": plan.goal,
                "status": plan.status,
                "total_steps": plan.total_steps,
                "completed_steps": plan.completed_steps,
                "failed_steps": plan.failed_steps,
                "is_running": str(plan.id) in self._active_tasks,
                "started_at": plan.started_at.isoformat() if plan.started_at else None,
                "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
                "created_at": plan.created_at.isoformat(),
                "steps": [
                    {
                        "id": str(s.id),
                        "step_number": s.step_number,
                        "description": s.description,
                        "tool_name": s.tool_name,
                        "status": s.status,
                        "result": s.result,
                        "error": s.error,
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    }
                    for s in plan.steps
                ],
            }

    async def list_queue(self) -> list[dict[str, Any]]:
        """List all active and recently completed plans in the queue."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan)
                .order_by(TaskPlan.created_at.desc())
                .limit(50)
            )
            plans = result.scalars().all()

            return [
                {
                    "id": str(p.id),
                    "goal": p.goal[:100],
                    "status": p.status,
                    "total_steps": p.total_steps,
                    "completed_steps": p.completed_steps,
                    "failed_steps": p.failed_steps,
                    "is_running": str(p.id) in self._active_tasks,
                    "created_at": p.created_at.isoformat(),
                    "started_at": p.started_at.isoformat() if p.started_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                }
                for p in plans
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get worker pool statistics."""
        return {
            "max_workers": self._max_workers,
            "active_plans": len(self._active_tasks),
            "available_worker_slots": max(0, self._max_workers - len(self._active_tasks)),
            "plan_ids": list(self._active_tasks.keys()),
        }

    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a running plan by its ID."""
        cancel_event = self._cancel_events.get(plan_id)
        if cancel_event:
            cancel_event.set()

        task = self._active_tasks.get(plan_id)
        if task and not task.done():
            task.cancel()
            del self._active_tasks[plan_id]
            logger.info("Plan cancelled", plan_id=plan_id)
            return True

        # If not in active tasks, try to mark as cancelled in DB
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            if plan and plan.status in ("running", "pending"):
                plan.status = "cancelled"
                plan.completed_at = datetime.now(UTC)
                await db.commit()
                return True

        return False

    async def cancel_all(self) -> int:
        """Cancel all running plans. Returns count cancelled."""
        count = 0
        for plan_id, task in list(self._active_tasks.items()):
            cancel_event = self._cancel_events.get(plan_id)
            if cancel_event:
                cancel_event.set()
            if not task.done():
                task.cancel()
                count += 1
        self._active_tasks.clear()
        logger.info("All plans cancelled", count=count)
        return count

    # ------------------------------------------------------------------
    # Internal: execution
    # ------------------------------------------------------------------

    async def _execute_plan_with_semaphore(
        self,
        plan: TaskPlan,
        db: AsyncSession,
    ) -> TaskPlan:
        """Execute a plan's steps, respecting the semaphore."""
        async with self._semaphore:
            return await self._execute_plan_steps(plan)

    async def _execute_plan_steps(self, plan: TaskPlan) -> TaskPlan:
        """Execute all steps in a plan sequentially.

        Each step gets its own DB session for isolation.
        Handles cancellation, retries, and error modes.
        """
        plan_id_str = str(plan.id)
        cancel_event = self._cancel_events[plan_id_str]

        async with async_session_factory() as db:
            # Refresh plan from DB
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan.id)
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                logger.error("Plan not found in DB", plan_id=plan_id_str)
                return plan

            await db.refresh(plan, ["steps"])

            plan.status = "running"
            plan.started_at = datetime.now(UTC)
            await db.commit()

            steps = plan.steps or []
            plan.total_steps = len(steps)
            await db.commit()

            logger.info(
                "Executing plan",
                plan_id=plan_id_str,
                total_steps=len(steps),
            )

            for step in steps:
                # Check cancellation
                if cancel_event.is_set():
                    await self._mark_cancelled(plan, db)
                    return plan

                # Execute the step
                success = await self._execute_step(step, db, plan.max_retries)

                if success:
                    plan.completed_steps = (plan.completed_steps or 0) + 1
                else:
                    plan.failed_steps = (plan.failed_steps or 0) + 1
                    if plan.error_mode == "abort":
                        logger.info(
                            "Aborting plan due to step failure",
                            plan_id=plan_id_str,
                            step_number=step.step_number,
                        )
                        break

                await db.commit()

            # Determine final status
            if cancel_event.is_set():
                await self._mark_cancelled(plan, db)
            elif plan.failed_steps and plan.failed_steps == plan.total_steps:
                plan.status = "failed"
            elif plan.failed_steps and plan.failed_steps > 0:
                plan.status = "partially_completed"
            else:
                plan.status = "completed"

            plan.completed_at = datetime.now(UTC)
            await db.commit()

            logger.info(
                "Plan execution completed",
                plan_id=plan_id_str,
                status=plan.status,
                completed=plan.completed_steps,
                failed=plan.failed_steps,
                total=plan.total_steps,
            )

        # Clean up
        self._active_tasks.pop(plan_id_str, None)
        self._cancel_events.pop(plan_id_str, None)

        return plan

    async def _execute_step(
        self,
        step: TaskStep,
        db: AsyncSession,
        max_retries: int = 2,
    ) -> bool:
        """Execute a single step with retry logic."""
        last_error: str | None = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(
                    "Retrying step",
                    step_id=str(step.id),
                    attempt=attempt,
                )
                step.retry_count = (step.retry_count or 0) + 1

            step.status = "running"
            step.started_at = datetime.now(UTC)
            await db.commit()

            try:
                result = await self._executor.execute(
                    tool_name=step.tool_name,
                    arguments=step.tool_params or {},
                )

                if "error" in result:
                    raise RuntimeError(result["error"])

                step.status = "completed"
                step.result = result
                step.completed_at = datetime.now(UTC)
                await db.commit()
                return True

            except Exception as e:
                last_error = str(e)
                step.status = "failed"
                step.error = last_error
                step.completed_at = datetime.now(UTC)
                await db.commit()

                logger.warning(
                    "Step failed",
                    step_id=str(step.id),
                    tool_name=step.tool_name,
                    attempt=attempt,
                    error=last_error,
                )

                if attempt >= max_retries:
                    break

                await asyncio.sleep(1)

        step.status = "failed"
        step.error = last_error or "Unknown error"
        step.completed_at = datetime.now(UTC)
        await db.commit()
        return False

    async def _mark_cancelled(
        self,
        plan: TaskPlan,
        db: AsyncSession,
    ) -> None:
        """Mark a plan and its remaining steps as cancelled."""
        plan.status = "cancelled"
        plan.completed_at = datetime.now(UTC)

        for step in (plan.steps or []):
            if step.status in ("pending", "running"):
                step.status = "cancelled"
                step.completed_at = datetime.now(UTC)

        await db.commit()

        plan_id_str = str(plan.id)
        self._active_tasks.pop(plan_id_str, None)
        self._cancel_events.pop(plan_id_str, None)

        logger.info("Plan cancelled", plan_id=plan_id_str)


# Singleton
_engine: MultitaskingEngine | None = None


def get_multitasking_engine(max_workers: int = 5) -> MultitaskingEngine:
    """Get or create the multitasking engine singleton."""
    global _engine
    if _engine is None:
        _engine = MultitaskingEngine(max_concurrent_workers=max_workers)
    return _engine
"""Task Execution Engine — executes task plans step by step."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws import manager as ws_manager  # WebSocket connection manager
from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.task import TaskPlan, TaskStep
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)

# In-memory stop events for pause/cancel support
_stop_events: dict[str, asyncio.Event] = {}


def _get_stop_event(plan_id: str) -> asyncio.Event:
    """Get or create a stop event for a plan."""
    if plan_id not in _stop_events:
        _stop_events[plan_id] = asyncio.Event()
    return _stop_events[plan_id]


class TaskExecutionEngine:
    """Executes a TaskPlan by running steps sequentially.

    Reports progress via WebSocket events and manages pause/resume/cancel.
    """

    def __init__(self) -> None:
        self._tool_executor = ToolExecutor()

    async def execute_plan(self, plan_id: str, user_id: str) -> None:
        """Execute a task plan in the background.

        Args:
            plan_id: The UUID of the TaskPlan to execute.
            user_id: The UUID of the user who owns the plan.
        """
        logger.info("Starting plan execution", plan_id=plan_id)

        stop_event = _get_stop_event(plan_id)
        stop_event.clear()

        async with async_session_factory() as db:
            # Load plan with steps
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if plan is None:
                logger.error("Plan not found", plan_id=plan_id)
                return

            if plan.status != "approved":
                logger.warning(
                    "Plan not in approved state",
                    plan_id=plan_id,
                    status=plan.status,
                )
                return

            # Mark plan as running
            plan.status = "running"
            plan.started_at = datetime.now(UTC)
            await db.commit()

            # Notify via WebSocket
            await self._send_ws_event(user_id, {
                "type": "task_started",
                "plan_id": plan_id,
                "total_steps": len(plan.steps),
            })

            # Execute each step
            for step in plan.steps:
                # Check for cancellation
                if stop_event.is_set():
                    await self._handle_cancellation(plan, db, user_id)
                    return

                # Check for pause
                if await self._is_paused(plan_id):
                    await self._handle_pause(plan_id, plan, db, user_id)
                    # After resume, check cancel again
                    if stop_event.is_set():
                        await self._handle_cancellation(plan, db, user_id)
                        return

                await self._execute_step(plan, step, db, user_id)

            # Mark plan as completed
            plan.status = "completed"
            plan.completed_at = datetime.now(UTC)
            await db.commit()

            await self._send_ws_event(user_id, {
                "type": "task_completed",
                "plan_id": plan_id,
                "total_steps": plan.total_steps,
                "completed_steps": plan.completed_steps,
                "failed_steps": plan.failed_steps,
            })

            logger.info("Plan execution completed", plan_id=plan_id)

    async def _execute_step(
        self,
        plan: TaskPlan,
        step: TaskStep,
        db: AsyncSession,
        user_id: str,
    ) -> None:
        """Execute a single step with retry support."""
        logger.info(
            "Executing step",
            plan_id=str(plan.id),
            step_order=step.step_order,
            tool=step.tool_name,
        )

        # Mark step as running
        step.status = "running"
        step.started_at = datetime.now(UTC)
        await db.commit()

        await self._send_ws_event(user_id, {
            "type": "task_step_start",
            "plan_id": str(plan.id),
            "step_id": str(step.id),
            "step_order": step.step_order,
            "tool_name": step.tool_name,
            "description": step.description,
        })

        # Execute with retries
        max_retries = plan.max_retries
        for attempt in range(max_retries + 1):
            # Check for cancellation before each attempt
            if _stop_events.get(str(plan.id), asyncio.Event()).is_set():
                await self._handle_cancellation(plan, db, user_id)
                return

            try:
                result = await self._tool_executor.execute(
                    tool_name=step.tool_name,
                    arguments=step.tool_params,
                )

                # Check for errors in the result
                if "error" in result:
                    raise RuntimeError(result["error"])

                # Step succeeded
                step.status = "completed"
                step.result = result
                step.completed_at = datetime.now(UTC)
                plan.completed_steps += 1
                await db.commit()

                await self._send_ws_event(user_id, {
                    "type": "task_step_complete",
                    "plan_id": str(plan.id),
                    "step_id": str(step.id),
                    "step_order": step.step_order,
                    "result": result,
                })
                return

            except Exception as e:
                step.retry_count = attempt + 1
                error_msg = str(e)

                if attempt < max_retries and plan.error_mode != "abort":
                    logger.warning(
                        "Step failed, retrying",
                        plan_id=str(plan.id),
                        step=step.step_order,
                        attempt=attempt + 1,
                        error=error_msg,
                    )
                    await self._send_ws_event(user_id, {
                        "type": "task_step_retry",
                        "plan_id": str(plan.id),
                        "step_id": str(step.id),
                        "step_order": step.step_order,
                        "attempt": attempt + 1,
                        "error": error_msg,
                    })
                    await asyncio.sleep(1)  # Small delay before retry
                    continue

                # All retries exhausted
                if plan.error_mode == "skip":
                    step.status = "skipped"
                    step.error = error_msg
                    step.completed_at = datetime.now(UTC)
                    plan.failed_steps += 1
                    await db.commit()

                    await self._send_ws_event(user_id, {
                        "type": "task_step_skipped",
                        "plan_id": str(plan.id),
                        "step_id": str(step.id),
                        "step_order": step.step_order,
                        "error": error_msg,
                    })
                    return

                # Abort on failure (default)
                step.status = "failed"
                step.error = error_msg
                step.completed_at = datetime.now(UTC)
                plan.failed_steps += 1
                plan.status = "failed"
                plan.completed_at = datetime.now(UTC)
                await db.commit()

                await self._send_ws_event(user_id, {
                    "type": "task_step_failed",
                    "plan_id": str(plan.id),
                    "step_id": str(step.id),
                    "step_order": step.step_order,
                    "error": error_msg,
                })
                await self._send_ws_event(user_id, {
                    "type": "task_failed",
                    "plan_id": str(plan.id),
                    "error": error_msg,
                })
                return

    async def _handle_pause(
        self,
        plan_id: str,
        plan: TaskPlan,
        db: AsyncSession,
        user_id: str,
    ) -> None:
        """Handle pause — wait until resumed or cancelled."""
        plan.status = "paused"
        await db.commit()

        await self._send_ws_event(user_id, {
            "type": "task_paused",
            "plan_id": plan_id,
        })

        # Wait for resume or cancel
        stop_event = _stop_events.get(plan_id, asyncio.Event())
        while not stop_event.is_set():
            # Check if we should resume
            async with async_session_factory() as check_db:
                result = await check_db.execute(
                    select(TaskPlan).where(TaskPlan.id == plan_id)
                )
                current_plan = result.scalar_one_or_none()
                if current_plan and current_plan.status == "running":
                    break
            await asyncio.sleep(0.5)

        if stop_event.is_set():
            return  # Cancelled

        plan.status = "running"
        await db.commit()

        await self._send_ws_event(user_id, {
            "type": "task_resumed",
            "plan_id": plan_id,
        })

    async def _handle_cancellation(
        self,
        plan: TaskPlan,
        db: AsyncSession,
        user_id: str,
    ) -> None:
        """Handle cancellation — mark remaining steps as cancelled."""
        plan.status = "cancelled"
        plan.completed_at = datetime.now(UTC)

        for step in plan.steps:
            if step.status == "pending":
                step.status = "cancelled"
                step.completed_at = datetime.now(UTC)

        await db.commit()

        await self._send_ws_event(user_id, {
            "type": "task_cancelled",
            "plan_id": str(plan.id),
            "completed_steps": plan.completed_steps,
        })

    async def pause_plan(self, plan_id: str) -> bool:
        """Pause a running plan."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if plan is None or plan.status != "running":
                return False

            plan.status = "paused"
            await db.commit()
            return True

    async def resume_plan(self, plan_id: str) -> bool:
        """Resume a paused plan."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if plan is None or plan.status != "paused":
                return False

            plan.status = "running"
            await db.commit()
            return True

    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a running or paused plan."""
        event = _stop_events.get(plan_id)
        if event:
            event.set()

        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if plan is None:
                return False

            if plan.status not in ("running", "paused"):
                return False

            plan.status = "cancelled"
            plan.completed_at = datetime.now(UTC)
            await db.commit()
            return True

    async def _is_paused(self, plan_id: str) -> bool:
        """Check if a plan has been paused."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            return plan is not None and plan.status == "paused"

    async def _send_ws_event(self, user_id: str, event: dict[str, Any]) -> None:
        """Send a WebSocket event to the user."""
        try:
            # The ConnectionManager's send_json expects dict data
            await ws_manager.send_json(user_id, event)
        except Exception as e:
            logger.warning(
                "Failed to send WebSocket event",
                user_id=user_id,
                event_type=event.get("type"),
                error=str(e),
            )

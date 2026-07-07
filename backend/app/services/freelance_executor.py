"""Freelance Execution Engine — executes paid jobs using Jarvis's autonomous task system.

This module takes a paid FreelanceJob, uses the TaskPlanner to break the
customer's request into steps, and executes them through the TaskExecutionEngine.
Results are collected into the job's result_files and result_summary fields.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.api.ws import manager as ws_manager
from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.freelance_task import FreelanceJob
from app.models.task_plan import TaskPlan
from app.models.user import User
from app.services.task_executor import TaskExecutionEngine
from app.services.task_planner import TaskPlanner

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# System "freelancer" user — used to own the task plans created for jobs
# ---------------------------------------------------------------------------

FREELANCER_EMAIL = "freelancer@jarvis.local"
FREELANCER_USERNAME = "jarvis-freelancer"


async def _get_or_create_freelancer_user() -> User:
    """Get the dedicated freelancer system user, creating it if needed.

    This user owns all task plans generated for freelance jobs so they
    are traceable and don't pollute any customer's personal task history.
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.email == FREELANCER_EMAIL)
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        # Create the freelancer user
        import uuid

        from app.core.security import get_password_hash

        freelancer_id = uuid.uuid4()
        user = User(
            id=freelancer_id,
            email=FREELANCER_EMAIL,
            username=FREELANCER_USERNAME,
            hashed_password=get_password_hash(str(freelancer_id)),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created freelancer system user", user_id=str(user.id))
        return user


# ---------------------------------------------------------------------------
# Execution Engine
# ---------------------------------------------------------------------------


class FreelanceExecutionEngine:
    """Executes paid freelance jobs using Jarvis's autonomous task system.

    For each paid job:
    1. Gets the freelancer system user
    2. Builds a goal from the job's description and template
    3. Uses TaskPlanner.generate_plan() to break it into steps
    4. Auto-approves the plan (no user approval needed — they already paid)
    5. Runs through TaskExecutionEngine.execute_plan()
    6. Collects results into the job record
    """

    def __init__(self) -> None:
        self._task_planner = TaskPlanner()
        self._task_engine = TaskExecutionEngine()

    async def execute_job(self, job_id: str) -> None:
        """Execute a paid freelance job in the background.

        Args:
            job_id: The UUID of the FreelanceJob to execute.
        """
        logger.info("Starting freelance job execution", job_id=job_id)

        # Get the freelancer system user
        freelancer = await _get_or_create_freelancer_user()

        async with async_session_factory() as db:
            result = await db.execute(
                select(FreelanceJob).where(FreelanceJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job is None:
                logger.error("Freelance job not found", job_id=job_id)
                return

            if job.status != "paid":
                logger.warning(
                    "Job not in paid state",
                    job_id=job_id,
                    status=job.status,
                )
                return

            # Mark as in progress
            job.status = "in_progress"
            await db.commit()

            await self._send_ws_event(str(freelancer.id), {
                "type": "job_started",
                "job_id": job_id,
            })

        try:
            # Build a comprehensive goal from the job
            goal = job.description or ""
            if job.template_id:
                async with async_session_factory() as db:
                    from app.models.freelance_task import TaskTemplate
                    tpl_result = await db.execute(
                        select(TaskTemplate).where(TaskTemplate.id == job.template_id)
                    )
                    template = tpl_result.scalar_one_or_none()
                    if template:
                        goal = f"{template.name}: {job.description or template.description}"

            if not goal:
                goal = "Execute the requested freelance task."

            logger.info(
                "Generating task plan for freelance job",
                job_id=job_id,
                goal=goal[:100],
            )

            # Step 1: Generate a plan using the TaskPlanner
            async with async_session_factory() as db:
                plan = await self._task_planner.generate_plan(
                    goal=goal,
                    db=db,
                    user_id=freelancer.id,
                )

            if plan is None:
                await self._fail_job(job_id, str(freelancer.id), "Failed to generate task plan")
                return

            # Store the plan ID on the job
            async with async_session_factory() as db:
                result = await db.execute(
                    select(FreelanceJob).where(FreelanceJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    # Store plan_id as a string in result_files dict
                    result_files = job.result_files or {}
                    result_files["_plan_id"] = str(plan.id)
                    job.result_files = result_files
                    await db.commit()

            # Step 2: Auto-approve the plan (customer already paid)
            async with async_session_factory() as db:
                result = await db.execute(
                    select(TaskPlan).where(TaskPlan.id == plan.id)
                )
                plan = result.scalar_one_or_none()
                if plan:
                    plan.status = "approved"
                    await db.commit()

            # Step 3: Execute the plan
            await self._task_engine.execute_plan(str(plan.id), str(freelancer.id))

            # Step 4: Collect results
            await self._collect_job_results(job_id, str(freelancer.id), str(plan.id))

        except Exception as e:
            logger.error(
                "Freelance job execution failed",
                job_id=job_id,
                error=str(e),
            )
            await self._fail_job(job_id, str(freelancer.id), str(e))

    async def _collect_job_results(
        self,
        job_id: str,
        user_id: str,
        plan_id: str,
    ) -> None:
        """Collect results from the executed task plan and update the job."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FreelanceJob).where(FreelanceJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job is None:
                return

            # Load the plan with steps
            plan_result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == plan_id)
            )
            plan = plan_result.scalar_one_or_none()

            if plan is None:
                return

            # Collect step results
            result_files: dict[str, str] = {}
            step_summaries: list[str] = []

            for step in plan.steps:
                if step.status == "completed" and step.result:
                    summary = (
                        f"Step {step.step_number} ({step.tool_name}): "
                        f"{str(step.result)[:200]}"
                    )
                    step_summaries.append(summary)

                    # If the result contains a file path, collect it
                    step_result = step.result
                    if isinstance(step_result, str) and os.path.isfile(step_result):
                        result_files[f"step_{step.step_number}_{step.tool_name}"] = (
                            step_result
                        )
                    elif isinstance(step_result, dict):
                        for key, val in step_result.items():
                            if isinstance(val, str) and os.path.isfile(val):
                                result_files[f"{key}"] = val

            # If there were no file results but we have text results,
            # save the step summaries as the result
            if not result_files and step_summaries:
                result_files["_execution_log"] = "\n".join(step_summaries)

            # Update job status based on plan
            if plan.status == "completed":
                job.status = "completed"
            else:
                job.status = "failed"
                job.result_summary = (
                    f"Plan ended with status: {plan.status}. "
                    f"Completed {plan.completed_steps}/{plan.total_steps} steps."
                )

            if step_summaries:
                job.result_summary = "\n".join(step_summaries[:10])

            existing_files = job.result_files or {}
            existing_files.update(result_files)
            job.result_files = existing_files
            job.completed_at = datetime.now(UTC)
            await db.commit()

            await self._send_ws_event(user_id, {
                "type": "job_completed" if job.status == "completed" else "job_failed",
                "job_id": job_id,
                "status": job.status,
                "summary": job.result_summary,
            })

            logger.info(
                "Job execution completed",
                job_id=job_id,
                status=job.status,
                steps=len(step_summaries),
            )

    async def _fail_job(self, job_id: str, user_id: str, error: str) -> None:
        """Mark a job as failed with an error message."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FreelanceJob).where(FreelanceJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job:
                job.status = "failed"
                job.result_summary = f"Error: {error}"
                job.completed_at = datetime.now(UTC)
                await db.commit()

                await self._send_ws_event(user_id, {
                    "type": "job_failed",
                    "job_id": job_id,
                    "error": error,
                })

    async def _send_ws_event(self, user_id: str, event: dict[str, Any]) -> None:
        """Send a WebSocket event."""
        try:
            await ws_manager.send_json(user_id, event)
        except Exception as e:
            logger.warning(
                "Failed to send WebSocket event",
                user_id=user_id,
                event_type=event.get("type"),
                error=str(e),
            )

"""Freelance Execution Engine — executes paid jobs using Jarvis's tool system.

This module provides the core execution logic for each job type. It uses
the existing TaskPlanner and TaskExecutionEngine to break jobs into steps
and execute them, with job-type-specific orchestration logic.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.api.ws import manager as ws_manager
from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.freelance_job import FreelanceJob
from app.models.task_plan import TaskPlan
from app.services.task_executor import TaskExecutionEngine
from app.services.task_planner import TaskPlanner
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Task type definitions — each maps a job type to a tool set and template
# ---------------------------------------------------------------------------

TASK_TYPE_TOOLS: dict[str, list[str]] = {
    "app_testing": [
        "take_screenshot",
        "click_element",
        "type_text",
        "navigate_to",
        "get_element_text",
    ],
    "copywriting": [
        "generate_text",
        "write_file",
        "read_file",
    ],
    "web_research": [
        "navigate_to",
        "get_element_text",
        "take_screenshot",
        "write_file",
    ],
    "data_entry": [
        "type_text",
        "click_element",
        "navigate_to",
        "read_file",
        "write_file",
    ],
    "file_processing": [
        "read_file",
        "write_file",
        "list_directory",
    ],
}

TASK_TYPE_TEMPLATES: dict[str, str] = {
    "app_testing": (
        "Test the web application at the given URL. "
        "Navigate through the main flows, take screenshots of each page, "
        "click on interactive elements, and record your observations. "
        "Compile a test report with findings."
    ),
    "copywriting": (
        "Generate written content based on the provided brief. "
        "Write the content to a file and confirm the output."
    ),
    "web_research": (
        "Research the given topic by browsing the web. "
        "Navigate to relevant pages, extract key information, "
        "take screenshots of important findings, and compile "
        "a comprehensive research report."
    ),
    "data_entry": (
        "Fill in forms or process data according to the instructions. "
        "Navigate to the target page, enter data into fields, "
        "and save the output."
    ),
    "file_processing": (
        "Read the specified file, process it according to the instructions, "
        "and save the transformed output to a new file."
    ),
}


# ---------------------------------------------------------------------------
# Freelance Execution Engine
# ---------------------------------------------------------------------------


class FreelanceExecutionEngine:
    """Orchestrates the execution of freelance jobs.

    For each job, it:
    1. Creates a task plan using the TaskPlanner (LLM-based)
    2. Executes the plan using the TaskExecutionEngine
    3. Collects results and updates the job status
    """

    def __init__(self) -> None:
        self._task_planner = TaskPlanner()
        self._task_engine = TaskExecutionEngine()
        self._tool_executor = ToolExecutor()

    async def execute_job(self, job_id: str, user_id: str) -> None:
        """Execute a freelance job in the background.

        Args:
            job_id: The UUID of the FreelanceJob to execute.
            user_id: The UUID of the user who owns the job.
        """
        logger.info("Starting freelance job execution", job_id=job_id, user_id=user_id)

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

            # Mark job as in progress
            job.status = "in_progress"
            job.started_at = datetime.now(UTC)
            await db.commit()

            await self._send_ws_event(user_id, {
                "type": "job_started",
                "job_id": job_id,
                "task_type": job.task_type,
            })

        try:
            # Step 1: Generate a task plan from the job
            plan = await self._create_plan_from_job(job)

            if plan is None:
                await self._fail_job(job_id, user_id, "Failed to generate task plan")
                return

            # Store the plan ID on the job
            async with async_session_factory() as db:
                result = await db.execute(
                    select(FreelanceJob).where(FreelanceJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.plan_id = plan.id
                    await db.commit()

            # Step 2: Approve and execute the plan
            async with async_session_factory() as db:
                result = await db.execute(
                    select(TaskPlan).where(TaskPlan.id == plan.id)
                )
                plan = result.scalar_one_or_none()
                if plan:
                    plan.status = "approved"
                    await db.commit()

            # Step 3: Execute the plan
            await self._task_engine.execute_plan(str(plan.id), user_id)

            # Step 4: Collect results
            await self._collect_job_results(job_id, user_id)

        except Exception as e:
            logger.error(
                "Freelance job execution failed",
                job_id=job_id,
                error=str(e),
            )
            await self._fail_job(job_id, user_id, str(e))

    async def _create_plan_from_job(self, job: FreelanceJob) -> TaskPlan | None:
        """Create a task plan from a freelance job using the LLM task planner.

        Builds a goal from the job description and task type, then uses
        the TaskPlanner to generate steps.
        """
        # Build a comprehensive goal from the job
        template = TASK_TYPE_TEMPLATES.get(
            job.task_type,
            "Execute the following task: {description}",
        )

        goal = template.format(description=job.description)
        if job.input_data:
            input_summary = ", ".join(
                f"{k}: {v}" for k, v in job.input_data.items()
            )
            goal += f"\n\nInput data: {input_summary}"

        # Use the TaskPlanner to generate steps
        try:
            async with async_session_factory() as db:
                plan = await self._task_planner.generate_plan(
                    goal=goal,
                    db=db,
                    user_id=job.user_id,
                )
                return plan
        except Exception as e:
            logger.error("Failed to create task plan", job_id=str(job.id), error=str(e))
            return None

    async def _collect_job_results(self, job_id: str, user_id: str) -> None:
        """Collect results from the executed task plan and update the job."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FreelanceJob).where(FreelanceJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job is None or job.plan_id is None:
                return

            # Load the plan with steps
            plan_result = await db.execute(
                select(TaskPlan).where(TaskPlan.id == job.plan_id)
            )
            plan = plan_result.scalar_one_or_none()

            if plan is None:
                return

            # Collect step results
            result_files: list[str] = []
            step_summaries: list[str] = []

            for step in plan.steps:
                if step.status == "completed" and step.result:
                    step_summaries.append(
                        f"Step {step.step_number} ({step.tool_name}): {step.result[:200]}"
                    )
                    # If the result contains a file path, collect it
                    if isinstance(step.result, str) and os.path.isfile(step.result):
                        result_files.append(step.result)

            # Update job status
            if plan.status == "completed":
                job.status = "completed"
            else:
                job.status = "failed"
                job.error = f"Plan ended with status: {plan.status}"

            job.result_summary = "\n".join(step_summaries[:10])
            job.result_files = result_files
            job.completed_at = datetime.now(UTC)
            await db.commit()

            await self._send_ws_event(user_id, {
                "type": "job_completed" if job.status == "completed" else "job_failed",
                "job_id": job_id,
                "status": job.status,
                "summary": job.result_summary,
            })

    async def _fail_job(self, job_id: str, user_id: str, error: str) -> None:
        """Mark a job as failed with an error message."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FreelanceJob).where(FreelanceJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job:
                job.status = "failed"
                job.error = error
                job.completed_at = datetime.now(UTC)
                await db.commit()

                await self._send_ws_event(user_id, {
                    "type": "job_failed",
                    "job_id": job_id,
                    "error": error,
                })

    async def _send_ws_event(self, user_id: str, event: dict[str, Any]) -> None:
        """Send a WebSocket event to the user."""
        try:
            await ws_manager.send_json(user_id, event)
        except Exception as e:
            logger.warning(
                "Failed to send WebSocket event",
                user_id=user_id,
                event_type=event.get("type"),
                error=str(e),
            )

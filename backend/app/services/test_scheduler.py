"""Scheduled Test Runner — runs test plans on a schedule using the PipelineOrchestrator pattern.

Reuses the PipelineOrchestrator pattern from Phase 10 (knowledge feed scheduler).
Each configured test plan can run on a cron schedule (hourly, daily, on-demand).
The scheduler picks due plans, runs them via TestingEngine, and stores results.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.testing import TestResult, TestRun
from app.services.test_report import get_report_generator
from app.services.testing_engine import get_testing_engine

logger = get_logger(__name__)

# Default interval for scheduled runs
_DEFAULT_INTERVAL_HOURS = 24
_DEFAULT_TEST_URL = "http://localhost:3000"
_DEFAULT_CRITERIA = [
    {"criterion": "The page loads without errors", "test_type": "page_load"},
    {"criterion": "The page title or header is visible", "test_type": "element_visibility"},
]


class TestScheduler:
    """Orchestrates scheduled test runs on a configurable interval.

    Runs as an in-process background asyncio task. Each cycle:
    1. Checks for due test configurations
    2. Runs each due test via TestingEngine
    3. Generates HTML reports for completed runs
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._testing_engine = get_testing_engine()
        self._report_generator = get_report_generator()

        # Stats for monitoring
        self._last_run: datetime | None = None
        self._total_runs: int = 0
        self._total_errors: int = 0
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            logger.warning("TestScheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "TestScheduler started",
            interval_hours=_DEFAULT_INTERVAL_HOURS,
        )

    async def stop(self) -> None:
        """Stop the scheduler loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("TestScheduler stopped")

    async def run_once(
        self,
        url: str = _DEFAULT_TEST_URL,
        criteria: list[dict[str, Any]] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Run one test cycle.

        Args:
            url: Target URL to test.
            criteria: List of test criteria. Defaults to basic page load check.
            name: Optional name for this test run.
            user_id: Optional user ID to own the test run.

        Returns:
            A report dict with run_id, status, and outcomes.
        """
        criteria = criteria or _DEFAULT_CRITERIA
        # Use a system user ID if none provided (freelancer system user)
        if user_id is None:
            user_id = await self._get_system_user_id()

        run_id = uuid.uuid4()
        report: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": str(run_id),
            "url": url,
            "status": "pending",
            "passed": 0,
            "failed": 0,
            "total": len(criteria),
            "report_path": None,
        }

        try:
            # Create the test run in the database
            async with async_session_factory() as db:
                run = TestRun(
                    id=run_id,
                    user_id=uuid.UUID(user_id),
                    url=url,
                    name=name or f"Scheduled test: {url}",
                    status="pending",
                    total_tests=len(criteria),
                )
                db.add(run)
                await db.flush()

                for i, c in enumerate(criteria):
                    test_result = TestResult(
                        id=uuid.uuid4(),
                        run_id=run.id,
                        step_number=i + 1,
                        criterion=c.get("criterion", f"Test step {i + 1}"),
                        test_type=c.get("test_type", "element_visibility"),
                        passed=False,
                        duration_ms=0,
                    )
                    db.add(test_result)

                await db.commit()

            # Execute the test run
            await self._testing_engine.run_test_plan(str(run_id))

            # Generate report
            report_path = await self._report_generator.generate_report(str(run_id))

            # Get final status
            async with async_session_factory() as db:
                result = await db.execute(
                    select(TestRun).where(TestRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if run:
                    report["status"] = run.status
                    report["passed"] = run.passed
                    report["failed"] = run.failed
                    report["report_path"] = report_path

            self._total_runs += 1

            logger.info(
                "Scheduled test run completed",
                run_id=str(run_id),
                passed=report["passed"],
                failed=report["failed"],
                total=report["total"],
            )

        except Exception as e:
            logger.error("Scheduled test run failed", error=str(e))
            self._total_errors += 1
            self._last_error = str(e)
            report["status"] = "failed"
            report["error"] = str(e)

        # Always record the attempt time — even a failed run must advance the
        # schedule, otherwise _seconds_until_next_run() returns 5 forever and
        # the scheduler hammers the DB in a tight loop.
        self._last_run = datetime.now(UTC)

        return report

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main scheduler loop — runs until stopped."""
        # Run an initial cycle on startup
        logger.info("Running initial scheduled test cycle")
        try:
            await self.run_once()
        except Exception as e:
            logger.error("Initial test cycle failed", error=str(e))

        # Guarantee a baseline even if the initial cycle failed before the
        # internal try/except — otherwise _seconds_until_next_run() returns 5
        # forever and the loop hammers the DB.
        if self._last_run is None:
            self._last_run = datetime.now(UTC)

        # Schedule subsequent runs
        while self._running:
            delay = self._seconds_until_next_run()
            logger.debug(
                "Next scheduled test run",
                delay_hours=round(delay / 3600, 1),
                next_run=(
                    datetime.now(UTC) + timedelta(seconds=delay)
                ).isoformat(),
            )

            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

            if not self._running:
                break

            try:
                await self.run_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Test cycle failed — will retry on next schedule",
                    error=str(e),
                )

    def _seconds_until_next_run(self) -> float:
        """Calculate seconds until the next scheduled test run.

        In low-power mode, run every 48 hours instead of 24.
        """
        interval_hours = (
            48 if settings.low_power_mode else _DEFAULT_INTERVAL_HOURS
        )
        interval_seconds = interval_hours * 3600

        if self._last_run is None:
            return 5  # Initial delay

        elapsed = (datetime.now(UTC) - self._last_run).total_seconds()
        if elapsed >= interval_seconds:
            return 5  # Due now

        return interval_seconds - elapsed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_system_user_id(self) -> str:
        """Get or create a system user ID for automated test runs."""
        # Try to find the freelancer system user
        try:
            from app.models.user import User

            async with async_session_factory() as db:
                result = await db.execute(
                    select(User).where(User.email == "freelancer@jarvis.local")
                )
                user = result.scalar_one_or_none()
                if user:
                    return str(user.id)
        except Exception:
            pass

        # Fallback: generate a deterministic UUID for the system
        return "00000000-0000-0000-0000-000000000001"

    async def trigger_webhook_run(
        self,
        url: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger a test run from a CI webhook.

        Args:
            url: URL to test (overrides default).
            payload: Webhook payload for context.

        Returns:
            Report dict with run_id and status.
        """
        test_url = url or _DEFAULT_TEST_URL
        name = "CI-triggered test"
        if payload:
            repo = payload.get("repository", "")
            ref = payload.get("ref", "")
            if repo:
                name = f"CI test: {repo} ({ref or 'default'})"

        logger.info(
            "Webhook-triggered test run",
            url=test_url,
            name=name,
        )

        return await self.run_once(
            url=test_url,
            name=name,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Get current scheduler status for monitoring."""
        return {
            "running": self._running,
            "total_runs": self._total_runs,
            "total_errors": self._total_errors,
            "last_error": self._last_error,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "interval_hours": (
                48 if settings.low_power_mode else _DEFAULT_INTERVAL_HOURS
            ),
            "mode": "low-power" if settings.low_power_mode else "normal",
        }


# Global singleton
test_scheduler = TestScheduler()

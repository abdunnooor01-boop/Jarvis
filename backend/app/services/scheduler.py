"""Scheduled Crawler & Pipeline Orchestrator — automated knowledge feed pipeline.

Runs as an asyncio task in the FastAPI lifespan. On a configurable schedule:
1. Crawls all active feed sources via FeedCrawler.crawl_all()
2. Generates the weekly digest (if due)
3. Runs auto-registration of discovered tools

Configurable via environment variables:
- CRAWL_INTERVAL_HOURS: How often to crawl (default: 24, daily at 2 AM)
- DIGEST_DAY_OF_WEEK: 0=Mon, 6=Sun (default: 6, Sunday)
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.services.feed_crawler import FeedCrawler
from app.services.tool_discovery import ToolDiscovery

logger = get_logger(__name__)


class PipelineOrchestrator:
    """Orchestrates the knowledge feed pipeline on a configurable schedule.

    Runs as an in-process background asyncio task. Each cycle:
    1. Ensures default sources are seeded
    2. Crawls all active feed sources
    3. Runs tool discovery on new entries, auto-flagging high-confidence tools
    4. Generates weekly digest if the configured day has arrived
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._crawler = FeedCrawler()
        self._discovery = ToolDiscovery()

        # Stats for monitoring
        self._last_crawl: datetime | None = None
        self._last_digest: datetime | None = None
        self._last_discovery: datetime | None = None
        self._total_crawls: int = 0
        self._total_errors: int = 0
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            logger.warning("PipelineOrchestrator is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "PipelineOrchestrator started",
            crawl_interval_hours=settings.crawl_interval_hours,
            digest_day=settings.digest_day_of_week,
        )

    async def stop(self) -> None:
        """Stop the scheduler loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._crawler.close()
        logger.info("PipelineOrchestrator stopped")

    async def run_once(self) -> dict[str, Any]:
        """Run one full pipeline cycle.

        Returns a detailed report of what happened.
        """
        report: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "crawl": None,
            "discovery": None,
            "digest": None,
        }

        # Record the attempt time up-front so the scheduler sleeps until the
        # real next interval even when a cycle fails (prevents 5s tight-loop).
        self._last_crawl = datetime.now(UTC)
        # Step 1: Ensure default sources exist
        await self._crawler.ensure_default_sources()

        # Step 2: Crawl all active sources
        try:
            crawl_results = await self._crawler.crawl_all()
            entries_stored = sum(
                r.get("entries_stored", 0) for r in crawl_results
            )
            errors = [
                r.get("error") for r in crawl_results if r.get("error")
            ]

            report["crawl"] = {
                "sources_crawled": len(crawl_results),
                "entries_stored": entries_stored,
                "errors": errors,
            }
            self._total_crawls += 1

            if errors:
                self._total_errors += len(errors)
                self._last_error = errors[-1]

            logger.info(
                "Crawl cycle complete",
                sources=len(crawl_results),
                stored=entries_stored,
                errors=len(errors),
            )
        except Exception as e:
            logger.error("Crawl cycle failed", error=str(e))
            self._total_errors += 1
            self._last_error = str(e)
            report["crawl"] = {"error": str(e)}
            # Don't stop the pipeline — discovery and digest may still run

        # Step 3: Run tool discovery on new entries
        try:
            if report.get("crawl") and report["crawl"].get("entries_stored", 0) > 0:
                discovery_result = await self._discovery.scan_entries(
                    hours_back=24,
                    min_confidence="medium",
                )
                self._last_discovery = datetime.now(UTC)

                # Auto-flag high-confidence tools (skipped in low-power mode)
                flagged = 0
                if not settings.low_power_mode:
                    for tool in discovery_result.get("tools_found", []):
                        if tool.get("confidence") == "high":
                            try:
                                await self._discovery.flag_for_review(tool)
                                flagged += 1
                            except Exception as flag_err:
                                logger.warning(
                                    "Failed to flag tool",
                                    tool=tool.get("title"),
                                    error=str(flag_err),
                                )

                report["discovery"] = {
                    "entries_scanned": discovery_result["entries_scanned"],
                    "tools_found": len(discovery_result["tools_found"]),
                    "tools_flagged": flagged,
                }

                logger.info(
                    "Tool discovery complete",
                    scanned=discovery_result["entries_scanned"],
                    found=len(discovery_result["tools_found"]),
                    flagged=flagged,
                )
        except Exception as e:
            logger.error("Tool discovery failed", error=str(e))
            report["discovery"] = {"error": str(e)}

        # Step 4: Generate weekly digest if due
        if self._is_digest_due():
            try:
                digest = await self._crawler.generate_digest(
                    hours_back=168,
                    max_entries=50,
                )
                report["digest"] = {
                    "total_entries": digest["total_entries"],
                }
                self._last_digest = datetime.now(UTC)
                logger.info(
                    "Weekly digest generated",
                    entries=digest["total_entries"],
                )
            except Exception as e:
                logger.error("Digest generation failed", error=str(e))
                report["digest"] = {"error": str(e)}

        return report

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main scheduler loop — runs until stopped."""
        # Run an initial cycle on startup
        logger.info("Running initial pipeline cycle")
        try:
            await self.run_once()
        except Exception as e:
            logger.error("Initial pipeline cycle failed", error=str(e))

        # Calculate delay until next scheduled crawl (daily at 2 AM)
        while self._running:
            delay = self._seconds_until_next_crawl()
            logger.debug(
                "Next crawl scheduled",
                delay_hours=round(delay / 3600, 1),
                next_run=(datetime.now(UTC) + timedelta(seconds=delay)).isoformat(),
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
                    "Pipeline cycle failed — will retry on next schedule",
                    error=str(e),
                )

    def _seconds_until_next_crawl(self) -> float:
        """Calculate seconds until the next scheduled crawl.

        In low-power mode, crawl every 48 hours instead of 24.
        """
        interval_hours = 48 if settings.low_power_mode else settings.crawl_interval_hours
        interval_seconds = interval_hours * 3600

        if self._last_crawl is None:
            # First run — start immediately
            return 5  # 5 seconds for initial delay

        elapsed = (datetime.now(UTC) - self._last_crawl).total_seconds()
        if elapsed >= interval_seconds:
            return 5  # Due now, run immediately

        return interval_seconds - elapsed

    def _is_digest_due(self) -> bool:
        """Check if the weekly digest is due.

        Based on the configured DIGEST_DAY_OF_WEEK (0=Mon, 6=Sun).
        Only generates once per week.
        """
        if self._last_digest is None:
            return True

        now = datetime.now(UTC)
        if now.weekday() != settings.digest_day_of_week:
            return False

        # Only generate once per day (the configured day)
        last_digest_day = self._last_digest.date()
        today = now.date()
        return last_digest_day < today

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Get current scheduler status for monitoring."""
        effective_interval = 48 if settings.low_power_mode else settings.crawl_interval_hours
        return {
            "running": self._running,
            "total_crawls": self._total_crawls,
            "total_errors": self._total_errors,
            "last_error": self._last_error,
            "last_crawl": self._last_crawl.isoformat() if self._last_crawl else None,
            "last_digest": self._last_digest.isoformat() if self._last_digest else None,
            "last_discovery": (
                self._last_discovery.isoformat() if self._last_discovery else None
            ),
            "crawl_interval_hours": effective_interval,
            "digest_day_of_week": settings.digest_day_of_week,
            "mode": "low-power" if settings.low_power_mode else "normal",
        }


# Global singleton for the FastAPI lifespan
scheduler = PipelineOrchestrator()

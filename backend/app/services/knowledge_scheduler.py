"""KnowledgeScheduler — automated background pipeline for knowledge feeds.

Runs as an asyncio task in the FastAPI lifespan. Periodically:
1. Crawls all active feed sources
2. Runs tool discovery on new entries
3. Generates weekly digests

Graceful error handling: one failed crawl never stops future ones.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.services.feed_crawler import FeedCrawler
from app.services.tool_discovery import ToolDiscovery

logger = get_logger(__name__)


class KnowledgeScheduler:
    """Background scheduler that automates the knowledge feed pipeline.

    Starts a periodic loop that crawls sources, discovers tools, and
    generates digests. Designed to be run as an asyncio task in the
    FastAPI lifespan (startup → shutdown).
    """

    def __init__(
        self,
        crawl_interval_minutes: int = 60,
        discovery_interval_minutes: int = 360,
        digest_interval_hours: int = 168,
    ) -> None:
        self._crawl_interval = crawl_interval_minutes * 60
        self._discovery_interval = discovery_interval_minutes * 60
        self._digest_interval = digest_interval_hours * 3600

        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._last_crawl: datetime | None = None
        self._last_discovery: datetime | None = None
        self._last_digest: datetime | None = None

        self._crawler = FeedCrawler()
        self._discovery = ToolDiscovery()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler loop.

        Safe to call multiple times — only starts one loop.
        """
        if self._running:
            logger.warning("KnowledgeScheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("KnowledgeScheduler started")

    async def stop(self) -> None:
        """Stop the background scheduler loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._crawler.close()
        logger.info("KnowledgeScheduler stopped")

    async def run_once(self) -> dict[str, Any]:
        """Run one full pipeline cycle (crawl + discover + digest if due).

        Useful for manual triggering or initial seed on startup.
        """
        results: dict[str, Any] = {
            "crawl": None,
            "discovery": None,
            "digest": None,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Step 1: Ensure default sources exist
        await self._crawler.ensure_default_sources()

        # Step 2: Crawl all active sources
        try:
            crawl_results = await self._crawler.crawl_all()
            results["crawl"] = {
                "sources_crawled": len(crawl_results),
                "total_entries_found": sum(
                    r.get("entries_found", 0) for r in crawl_results
                ),
                "total_entries_stored": sum(
                    r.get("entries_stored", 0) for r in crawl_results
                ),
                "errors": [
                    r.get("error") for r in crawl_results if r.get("error")
                ],
            }
            self._last_crawl = datetime.now(UTC)
            logger.info(
                "Crawl cycle complete",
                sources=results["crawl"]["sources_crawled"],
                stored=results["crawl"]["total_entries_stored"],
            )
        except Exception as e:
            logger.error("Crawl cycle failed", error=str(e))
            results["crawl"] = {"error": str(e)}

        # Step 3: Run tool discovery if crawl had new entries
        if results.get("crawl") and results["crawl"].get("total_entries_stored", 0) > 0:
            try:
                discovery_result = await self._discovery.scan_entries(
                    hours_back=24,
                    min_confidence="medium",
                )
                results["discovery"] = {
                    "entries_scanned": discovery_result["entries_scanned"],
                    "tools_found": discovery_result["tools_found"],
                    "scan_time": discovery_result["scan_time_seconds"],
                }
                self._last_discovery = datetime.now(UTC)

                # Auto-flag high-confidence tools
                for tool in discovery_result.get("tools_found", []):
                    if tool.get("confidence") == "high":
                        try:
                            flag_result = await self._discovery.flag_for_review(tool)
                            logger.info(
                                "Auto-flagged tool for review",
                                tool=tool.get("title"),
                                result=flag_result.get("status"),
                            )
                        except Exception as flag_err:
                            logger.warning(
                                "Failed to flag tool",
                                tool=tool.get("title"),
                                error=str(flag_err),
                            )

                logger.info(
                    "Tool discovery complete",
                    scanned=discovery_result["entries_scanned"],
                    found=len(discovery_result["tools_found"]),
                )
            except Exception as e:
                logger.error("Tool discovery failed", error=str(e))
                results["discovery"] = {"error": str(e)}

        # Step 4: Generate digest if due
        if self._is_digest_due():
            try:
                digest = await self._crawler.generate_digest(
                    hours_back=168,
                    max_entries=50,
                )
                results["digest"] = {
                    "total_entries": digest["total_entries"],
                    "generated_at": digest["generated_at"],
                }
                self._last_digest = datetime.now(UTC)
                logger.info(
                    "Weekly digest generated",
                    entries=digest["total_entries"],
                )
            except Exception as e:
                logger.error("Digest generation failed", error=str(e))
                results["digest"] = {"error": str(e)}

        return results

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main scheduler loop — runs until stopped."""
        logger.info(
            "Knowledge scheduler loop started",
            crawl_interval_s=self._crawl_interval,
            discovery_interval_s=self._discovery_interval,
        )

        # Run an initial cycle on startup
        try:
            await self.run_once()
        except Exception as e:
            logger.error("Initial scheduler cycle failed", error=str(e))

        # Periodic loop
        while self._running:
            try:
                await asyncio.sleep(self._crawl_interval)

                if not self._running:
                    break

                await self.run_once()

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(
                    "Scheduler cycle failed — will retry",
                    error=str(e),
                    next_retry_s=self._crawl_interval,
                )
                # Don't break the loop — retry on next interval

    def _is_digest_due(self) -> bool:
        """Check if a weekly digest is due."""
        if self._last_digest is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_digest).total_seconds()
        return elapsed >= self._digest_interval

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Get current scheduler status."""
        return {
            "running": self._running,
            "last_crawl": self._last_crawl.isoformat() if self._last_crawl else None,
            "last_discovery": (
                self._last_discovery.isoformat() if self._last_discovery else None
            ),
            "last_digest": self._last_digest.isoformat() if self._last_digest else None,
            "crawl_interval_minutes": self._crawl_interval // 60,
            "discovery_interval_minutes": self._discovery_interval // 60,
            "digest_interval_hours": self._digest_interval // 3600,
        }


# Global singleton for the FastAPI lifespan
scheduler = KnowledgeScheduler()

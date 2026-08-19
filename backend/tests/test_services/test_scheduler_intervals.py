"""Regression tests for scheduler interval math (the "5s tight-loop" bug).

Both schedulers previously computed `_seconds_until_next_*` by anchoring on a
last-run timestamp that was only updated AFTER a successful cycle. Any failure
(notably the `'str' object has no attribute 'hex'` UUID-binding error) left the
anchor stale, so the loop returned ~5s forever and spammed the DB/logs.

The fix records the attempt time (``_last_crawl``/``_last_run``) at the START of
each cycle, so the next delay is the real remaining interval even on failure.

These are pure unit tests of the interval math (no DB / network).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.services.scheduler import PipelineOrchestrator
from app.services.test_scheduler import _DEFAULT_INTERVAL_HOURS, TestScheduler


def _expected_interval_hours(test_scheduler: bool) -> int:
    if test_scheduler:
        return 48 if settings.low_power_mode else _DEFAULT_INTERVAL_HOURS
    return 48 if settings.low_power_mode else settings.crawl_interval_hours


def test_pipeline_initial_delay_is_short() -> None:
    orch = PipelineOrchestrator()
    assert orch._last_crawl is None
    assert orch._seconds_until_next_crawl() == 5


def test_pipeline_delay_respects_configured_interval() -> None:
    orch = PipelineOrchestrator()
    orch._last_crawl = datetime.now(UTC)
    interval = _expected_interval_hours(test_scheduler=False) * 3600
    delay = orch._seconds_until_next_crawl()
    # After a cycle has run, the next crawl must be the full interval away,
    # NOT ~5s — this is the core regression guard.
    assert interval - 60 <= delay <= interval


def test_pipeline_due_immediately_when_late() -> None:
    orch = PipelineOrchestrator()
    orch._last_crawl = datetime.now(UTC) - timedelta(days=3)
    assert orch._seconds_until_next_crawl() == 5


def test_test_scheduler_initial_delay_is_short() -> None:
    sched = TestScheduler()
    assert sched._last_run is None
    assert sched._seconds_until_next_run() == 5


def test_test_scheduler_delay_respects_configured_interval() -> None:
    sched = TestScheduler()
    sched._last_run = datetime.now(UTC)
    interval = _expected_interval_hours(test_scheduler=True) * 3600
    delay = sched._seconds_until_next_run()
    assert interval - 60 <= delay <= interval


def test_test_scheduler_due_immediately_when_late() -> None:
    sched = TestScheduler()
    sched._last_run = datetime.now(UTC) - timedelta(days=3)
    assert sched._seconds_until_next_run() == 5


@pytest.mark.asyncio
async def test_pipeline_failed_cycle_still_advances_last_crawl() -> None:
    """A failing cycle must still record the attempt time up-front.

    Regression for the 5s tight-loop: if `_last_crawl` only updated after a
    successful cycle, any failure (e.g. the UUID `hex` binding error) left it
    stale, so `_seconds_until_next_crawl` returned ~5s forever.
    """
    orch = PipelineOrchestrator()

    async def _boom() -> None:
        raise RuntimeError("simulated crawl failure")

    orch._crawler.ensure_default_sources = _boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await orch.run_once()

    assert orch._last_crawl is not None
    interval = _expected_interval_hours(test_scheduler=False) * 3600
    delay = orch._seconds_until_next_crawl()
    assert interval - 60 <= delay <= interval

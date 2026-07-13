"""Testing API routes — test run creation, execution, reports, and webhook triggers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.testing import TestResult, TestRun
from app.models.user import User
from app.schemas.testing import (
    TestRunActionResponse,
    TestRunCreate,
    TestRunListResponse,
    TestRunResponse,
    TestRunStatusResponse,
    WebhookPayload,
    WebhookTriggerResponse,
)
from app.services.test_report import get_report_generator
from app.services.testing_engine import get_testing_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/testing", tags=["testing"])

# Singleton
_testing_engine = get_testing_engine()
_report_generator = get_report_generator()


# ---------------------------------------------------------------------------
# Helper: ORM -> Response
# ---------------------------------------------------------------------------

def _run_to_response(run: TestRun) -> TestRunResponse:
    """Convert a TestRun ORM object to a response schema."""
    return TestRunResponse(
        id=run.id,
        user_id=run.user_id,
        url=run.url,
        name=run.name,
        status=run.status,
        total_tests=run.total_tests,
        passed=run.passed,
        failed=run.failed,
        report_path=run.report_path,
        results=[_result_to_response(r) for r in (run.results or [])],
        created_at=str(run.created_at),
        updated_at=str(run.updated_at),
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
    )


def _result_to_response(result: TestResult) -> dict[str, Any]:
    """Convert a TestResult ORM object to a dict for the response."""
    return {
        "id": result.id,
        "run_id": result.run_id,
        "step_number": result.step_number,
        "criterion": result.criterion,
        "test_type": result.test_type,
        "passed": result.passed,
        "detail": result.detail,
        "screenshot_path": result.screenshot_path,
        "duration_ms": result.duration_ms,
        "created_at": str(result.created_at),
    }


def _run_to_status(run: TestRun) -> TestRunStatusResponse:
    """Convert a TestRun to a lightweight status response."""
    progress = 0.0
    if run.total_tests > 0:
        completed = run.passed + run.failed
        progress = completed / run.total_tests

    return TestRunStatusResponse(
        id=run.id,
        url=run.url,
        name=run.name,
        status=run.status,
        total_tests=run.total_tests,
        passed=run.passed,
        failed=run.failed,
        report_path=run.report_path,
        progress=progress,
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_test_run(
    body: TestRunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunResponse:
    """Create a new test run with criteria and start execution immediately.

    Accepts a URL and a list of test criteria. Each criterion is a
    description of what to verify (e.g. "The login button should be visible")
    with a test type (page_load, element_visibility, text_content, etc.).
    """
    # Convert criteria to the format expected by the engine
    criteria = [
        {"criterion": c.criterion, "test_type": c.test_type}
        for c in body.criteria
    ]

    # Create the test run in the database
    run = await _testing_engine.create_test_run(
        user_id=current_user.id,
        url=body.url,
        criteria=criteria,
        name=body.name,
        db=db,
    )

    # Start execution in the background
    import asyncio

    asyncio.create_task(
        _testing_engine.run_test_plan(str(run.id))
    )

    logger.info(
        "Test run created and started",
        run_id=str(run.id),
        user_id=str(current_user.id),
        url=body.url[:80],
        criteria_count=len(criteria),
    )

    return _run_to_response(run)


@router.get("/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunResponse:
    """Get the full details and results of a test run."""
    result = await db.execute(
        select(TestRun).where(
            TestRun.id == run_id,
            TestRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    return _run_to_response(run)


@router.get("/{run_id}/status", response_model=TestRunStatusResponse)
async def get_test_run_status(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunStatusResponse:
    """Get the lightweight status of a test run (suitable for polling).

    Returns progress (0.0 to 1.0) and current status without
    full result details.
    """
    result = await db.execute(
        select(TestRun).where(
            TestRun.id == run_id,
            TestRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    return _run_to_status(run)


@router.get("", response_model=TestRunListResponse)
async def list_test_runs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunListResponse:
    """List all test runs for the current user with pagination."""
    # Get total count
    count_result = await db.execute(
        select(func.count(TestRun.id)).where(TestRun.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    # Get paginated runs
    offset = (page - 1) * page_size
    result = await db.execute(
        select(TestRun)
        .where(TestRun.user_id == current_user.id)
        .order_by(TestRun.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    runs = result.scalars().all()

    return TestRunListResponse(
        items=[_run_to_response(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/{run_id}/rerun", response_model=TestRunActionResponse)
async def rerun_test_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunActionResponse:
    """Rerun a previously completed test run with the same criteria."""
    result = await db.execute(
        select(TestRun).where(
            TestRun.id == run_id,
            TestRun.user_id == current_user.id,
        )
    )
    old_run = result.scalar_one_or_none()

    if old_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Recreate the criteria from the old run's results
    criteria = [
        {"criterion": r.criterion, "test_type": r.test_type}
        for r in (old_run.results or [])
    ]

    if not criteria:
        # Fallback to a basic page load test
        criteria = [
            {"criterion": "The page loads without errors", "test_type": "page_load"}
        ]

    # Create a new run
    new_run = await _testing_engine.create_test_run(
        user_id=current_user.id,
        url=old_run.url,
        criteria=criteria,
        name=f"{old_run.name or 'Rerun'} (rerun)",
        db=db,
    )

    # Start execution
    import asyncio

    asyncio.create_task(
        _testing_engine.run_test_plan(str(new_run.id))
    )

    logger.info(
        "Test run rerun created",
        original_run_id=str(run_id),
        new_run_id=str(new_run.id),
    )

    return TestRunActionResponse(
        run_id=new_run.id,
        status="running",
        message="Test run rerun has been started",
    )


@router.post("/{run_id}/report", response_model=TestRunActionResponse)
async def generate_test_report(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunActionResponse:
    """Generate or regenerate the HTML report for a test run."""
    result = await db.execute(
        select(TestRun).where(
            TestRun.id == run_id,
            TestRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    if run.status not in ("completed", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot generate report for a run in '{run.status}' state",
        )

    report_path = await _report_generator.generate_report(str(run_id), db=db)

    if report_path is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        )

    return TestRunActionResponse(
        run_id=run.id,
        status=run.status,
        message=f"Report generated at: {report_path}",
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a test run and all its results."""
    result = await db.execute(
        select(TestRun).where(
            TestRun.id == run_id,
            TestRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    await db.delete(run)
    await db.commit()

    logger.info("Test run deleted", run_id=str(run_id))


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@router.post("/webhook", response_model=WebhookTriggerResponse)
async def test_webhook(
    body: WebhookPayload,
) -> WebhookTriggerResponse:
    """Accept a CI webhook (GitHub Actions, etc.) to trigger a test run.

    Accepts a webhook payload with optional URL, ref, and repository info.
    Triggers a test run against the specified URL (or the default) and
    returns the run ID for status polling.
    """
    from app.services.test_scheduler import test_scheduler

    # Determine the URL to test
    test_url = body.url or "http://localhost:3000"

    # Build payload dict for context
    payload = {
        "url": test_url,
        "ref": body.ref,
        "event": body.event,
        "repository": body.repository,
        "commit_sha": body.commit_sha,
        **body.extra,
    }

    # Trigger the webhook run
    report = await test_scheduler.trigger_webhook_run(
        url=test_url,
        payload=payload,
    )

    run_id = report.get("run_id", "")
    report_url = report.get("report_path")

    logger.info(
        "Webhook-triggered test run created",
        run_id=run_id,
        url=test_url,
        event=body.event or "unknown",
        repository=body.repository or "unknown",
    )

    return WebhookTriggerResponse(
        run_id=uuid.UUID(run_id) if run_id else uuid.uuid4(),
        status="running",
        message="Test run triggered by webhook",
        report_url=report_url,
    )


# ---------------------------------------------------------------------------
# Scheduler status (admin)
# ---------------------------------------------------------------------------


@router.get("/scheduler/status")
async def get_scheduler_status() -> dict[str, Any]:
    """Get the status of the background test scheduler.

    This endpoint is not auth-protected for monitoring simplicity.
    In production, add admin-only access.
    """
    from app.services.test_scheduler import test_scheduler

    return test_scheduler.get_status()

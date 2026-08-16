"""SaaS Testing Service API — plans, runs, results, subscriptions, webhooks, and scheduler."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.testing import TestPlan, TestResult, TestRun, TestSubscription
from app.models.user import User
from app.schemas.testing import (
    TIER_INFO,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    TestCriterionCreate,
    TestPlanCreateRequest,
    TestPlanListResponse,
    TestPlanResponse,
    TestPlanUpdateRequest,
    TestResultResponse,
    TestRunActionResponse,
    TestRunCreateRequest,
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
# Helpers: ORM -> Response
# ---------------------------------------------------------------------------


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


def _run_to_response(run: TestRun) -> TestRunResponse:
    """Convert a TestRun ORM object to the full response schema."""
    return TestRunResponse(
        id=run.id,
        plan_id=run.plan_id,
        user_id=run.user_id,
        url=run.url,
        name=run.name,
        status=run.status,
        total_tests=run.total_tests,
        passed=run.passed,
        failed=run.failed,
        report_path=run.report_path,
        results_json=run.results_json or {},
        screenshots=run.screenshots or [],
        error_message=run.error_message,
        summary=run.summary,
        results=[_result_to_response(r) for r in (run.results or [])],
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
        created_at=str(run.created_at),
        updated_at=str(run.updated_at),
    )


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


def _plan_to_response(plan: TestPlan) -> dict[str, Any]:
    """Convert a TestPlan ORM object to a response dict."""
    return {
        "id": plan.id,
        "customer_id": plan.customer_id,
        "name": plan.name,
        "url": plan.url,
        "test_criteria": plan.test_criteria,
        "schedule": plan.schedule,
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


def _sub_to_response(sub: TestSubscription) -> dict[str, Any]:
    """Convert a TestSubscription ORM object to a response dict."""
    return {
        "id": sub.id,
        "customer_id": sub.customer_id,
        "tier": sub.tier,
        "status": sub.status,
        "stripe_subscription_id": sub.stripe_subscription_id,
        "stripe_customer_id": sub.stripe_customer_id,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "created_at": sub.created_at.isoformat(),
        "updated_at": sub.updated_at.isoformat(),
    }


# ------------------------------------------------------------------ #
#  Stripe helpers
# ------------------------------------------------------------------ #


async def _create_stripe_subscription(
    customer_email: str,
    tier: str,
) -> dict[str, Any]:
    """Create a Stripe subscription and return the checkout URL.

    Falls back gracefully if Stripe is not configured (test/dev mode).
    """
    if not settings.stripe_secret_key:
        logger.warning(
            "Stripe not configured — returning mock subscription URL",
            tier=tier,
        )
        return {
            "subscription_id": f"mock_sub_{uuid.uuid4().hex[:12]}",
            "checkout_url": None,
            "mock": True,
        }

    try:
        import stripe as stripe_lib

        stripe_lib.api_key = settings.stripe_secret_key

        # Look up or create the Stripe price for this tier
        tier_config = TIER_INFO.get(tier, TIER_INFO["basic"])
        price_data = stripe_lib.Price.create(
            unit_amount=tier_config.price_monthly_cents,
            currency="usd",
            recurring={"interval": "month"},
            product_data={
                "name": f"Jarvis Testing - {tier_config.name}",
                "description": tier_config.description,
            },
        )

        # Create a checkout session
        session = stripe_lib.checkout.Session.create(
            customer_email=customer_email,
            mode="subscription",
            line_items=[{"price": price_data.id, "quantity": 1}],
            success_url=f"{settings.app_base_url or 'http://localhost:3000'}/testing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.app_base_url or 'http://localhost:3000'}/testing/pricing",
        )

        return {
            "subscription_id": session.id,
            "checkout_url": session.url,
            "mock": False,
        }
    except Exception as e:
        logger.error("Failed to create Stripe subscription", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment processing error: {e!s}",
        ) from e


# ---------------------------------------------------------------------------
#  Run Endpoints (direct)
# ---------------------------------------------------------------------------


@router.post("", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_test_run(
    body: TestRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestRunResponse:
    """Create a new test run with criteria and start execution immediately.

    Accepts a URL and a list of test criteria. Each criterion is a
    description of what to verify (e.g. "The login button should be visible")
    with a test type (page_load, element_visibility, text_content, etc.).
    """
    criteria = [
        {"criterion": c.criterion, "test_type": c.test_type}
        for c in body.criteria
    ]

    run = await _testing_engine.create_test_run(
        user_id=current_user.id,
        url=body.url,
        criteria=criteria,
        name=body.name,
        db=db,
    )

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
    count_result = await db.execute(
        select(func.count(TestRun.id)).where(TestRun.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

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

    criteria = [
        {"criterion": r.criterion, "test_type": r.test_type}
        for r in (old_run.results or [])
    ]

    if not criteria:
        criteria = [
            {"criterion": "The page loads without errors", "test_type": "page_load"}
        ]

    new_run = await _testing_engine.create_test_run(
        user_id=current_user.id,
        url=old_run.url,
        criteria=criteria,
        name=f"{old_run.name or 'Rerun'} (rerun)",
        db=db,
    )

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


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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
    """Accept a CI webhook (GitHub Actions, etc.) to trigger a test run."""
    from app.services.test_scheduler import test_scheduler

    test_url = body.url or "http://localhost:3000"

    payload = {
        "url": test_url,
        "ref": body.ref,
        "event": body.event,
        "repository": body.repository,
        "commit_sha": body.commit_sha,
        **body.extra,
    }

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

    Not auth-protected for monitoring simplicity.
    In production, add admin-only access.
    """
    from app.services.test_scheduler import test_scheduler

    return test_scheduler.get_status()


# ------------------------------------------------------------------ #
#  Test Plan Endpoints
# ------------------------------------------------------------------ #


@router.post("/plans", response_model=TestPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_test_plan(
    request: TestPlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new test plan for the authenticated user."""
    sub_result = await db.execute(
        select(TestSubscription).where(
            TestSubscription.customer_id == current_user.id,
            TestSubscription.status == "active",
        )
    )
    subscription = sub_result.scalar_one_or_none()

    if subscription:
        tier_config = TIER_INFO.get(subscription.tier, TIER_INFO["basic"])
        plan_count_result = await db.execute(
            select(func.count(TestPlan.id)).where(
                TestPlan.customer_id == current_user.id,
                TestPlan.status == "active",
            )
        )
        plan_count = plan_count_result.scalar() or 0
        if plan_count >= tier_config.max_plans:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your {subscription.tier} tier allows maximum {tier_config.max_plans} active plans. Upgrade to Pro.",
            )

    plan = TestPlan(
        customer_id=current_user.id,
        name=request.name,
        url=request.url,
        test_criteria=request.test_criteria,
        schedule=request.schedule,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    logger.info("Test plan created", plan_id=str(plan.id), user_id=str(current_user.id))
    return _plan_to_response(plan)


@router.get("/plans", response_model=TestPlanListResponse)
async def list_test_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List test plans for the authenticated user."""
    query = select(TestPlan).where(TestPlan.customer_id == current_user.id)

    if status_filter:
        query = query.where(TestPlan.status == status_filter)

    query = query.order_by(TestPlan.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    plans = result.scalars().all()

    return {
        "items": [_plan_to_response(p) for p in plans],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/plans/{plan_id}", response_model=TestPlanResponse)
async def get_test_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get details for a specific test plan."""
    result = await db.execute(
        select(TestPlan).where(
            TestPlan.id == plan_id,
            TestPlan.customer_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )
    return _plan_to_response(plan)


@router.put("/plans/{plan_id}", response_model=TestPlanResponse)
async def update_test_plan(
    plan_id: uuid.UUID,
    request: TestPlanUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Update an existing test plan."""
    result = await db.execute(
        select(TestPlan).where(
            TestPlan.id == plan_id,
            TestPlan.customer_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)

    await db.commit()
    await db.refresh(plan)
    return _plan_to_response(plan)


# ------------------------------------------------------------------ #
#  Plan-triggered Run Endpoints
# ------------------------------------------------------------------ #


@router.post("/plans/{plan_id}/run", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_test_run(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger a new test run for a given plan."""
    result = await db.execute(
        select(TestPlan).where(
            TestPlan.id == plan_id,
            TestPlan.customer_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    sub_result = await db.execute(
        select(TestSubscription).where(
            TestSubscription.customer_id == current_user.id,
            TestSubscription.status == "active",
        )
    )
    subscription = sub_result.scalar_one_or_none()
    if subscription:
        tier_config = TIER_INFO.get(subscription.tier, TIER_INFO["basic"])
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        run_count_result = await db.execute(
            select(func.count(TestRun.id)).where(
                TestRun.plan_id == plan_id,
                TestRun.created_at >= month_start,
            )
        )
        run_count = run_count_result.scalar() or 0
        if run_count >= tier_config.max_runs_per_month:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Monthly run limit ({tier_config.max_runs_per_month}) reached. Upgrade tier or wait for next billing period.",
            )

    test_run = TestRun(
        plan_id=plan_id,
        user_id=current_user.id,
        url=plan.url,
        status="pending",
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    logger.info(
        "Test run triggered",
        run_id=str(test_run.id),
        plan_id=str(plan_id),
        user_id=str(current_user.id),
    )
    return _run_to_response(test_run)


@router.get("/runs", response_model=TestRunListResponse)
async def list_test_runs_by_plan(
    plan_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List test runs, optionally filtered by plan."""
    query = (
        select(TestRun)
        .join(TestPlan, TestRun.plan_id == TestPlan.id)
        .where(TestPlan.customer_id == current_user.id)
    )

    if plan_id:
        query = query.where(TestRun.plan_id == plan_id)

    query = query.order_by(TestRun.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    runs = result.scalars().all()

    return {
        "items": [_run_to_response(r) for r in runs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/runs/{run_id}", response_model=TestRunResponse)
async def get_test_run_by_plan(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get details for a specific test run (via plan ownership)."""
    result = await db.execute(
        select(TestRun)
        .join(TestPlan, TestRun.plan_id == TestPlan.id)
        .where(
            TestRun.id == run_id,
            TestPlan.customer_id == current_user.id,
        )
    )
    test_run = result.scalar_one_or_none()
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    return _run_to_response(test_run)


# ------------------------------------------------------------------ #
#  Subscription Endpoints
# ------------------------------------------------------------------ #


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current user's subscription."""
    result = await db.execute(
        select(TestSubscription).where(TestSubscription.customer_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )
    return _sub_to_response(subscription)


@router.post("/subscription", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request: SubscriptionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create or update a subscription for the authenticated user."""
    if request.tier not in TIER_INFO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier '{request.tier}'. Valid tiers: {', '.join(TIER_INFO.keys())}",
        )

    result = await db.execute(
        select(TestSubscription).where(TestSubscription.customer_id == current_user.id)
    )
    existing = result.scalar_one_or_none()

    stripe_result = await _create_stripe_subscription(
        customer_email=current_user.email,
        tier=request.tier,
    )

    if existing:
        existing.tier = request.tier
        if not stripe_result.get("mock"):
            existing.stripe_subscription_id = stripe_result.get("subscription_id")
        if existing.status == "incomplete" and stripe_result.get("mock"):
            existing.status = "active"
        await db.commit()
        await db.refresh(existing)
        subscription = existing
    else:
        sub = TestSubscription(
            customer_id=current_user.id,
            tier=request.tier,
            status="active" if stripe_result.get("mock") else "incomplete",
            stripe_subscription_id=stripe_result.get("subscription_id"),
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        subscription = sub

    logger.info(
        "Subscription created/updated",
        user_id=str(current_user.id),
        tier=request.tier,
        mock=stripe_result.get("mock", False),
    )
    return _sub_to_response(subscription)


# ------------------------------------------------------------------ #
#  Tier info endpoint (public)
# ------------------------------------------------------------------ #


@router.get("/tiers")
async def list_tiers() -> dict[str, Any]:
    """List available subscription tiers with pricing."""
    return {
        "tiers": {
            key: {
                "name": info.name,
                "price_monthly_cents": info.price_monthly_cents,
                "price_monthly_dollars": round(info.price_monthly_cents / 100, 2),
                "max_plans": info.max_plans,
                "max_runs_per_month": info.max_runs_per_month,
                "description": info.description,
            }
            for key, info in TIER_INFO.items()
        }
    }
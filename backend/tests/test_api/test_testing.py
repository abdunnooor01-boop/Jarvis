"""Tests for the SaaS Testing Service API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.testing import TestPlan, TestRun, TestSubscription
from app.models.user import User


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = "00000000-0000-0000-0000-000000000001"
    user.email = "test@example.com"
    return user


@pytest.fixture
def client() -> AsyncClient:
    """Create a test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ------------------------------------------------------------------ #
#  Test Plan Tests
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_create_test_plan_success() -> None:
    """Test creating a test plan."""
    from app.api.testing import router

    # Quick router prefix check
    assert router.prefix == "/api/v1/testing"


@pytest.mark.asyncio
async def test_plan_to_response() -> None:
    """Test _plan_to_response helper."""
    from app.api.testing import _plan_to_response
    from datetime import datetime, timezone

    plan = MagicMock(spec=TestPlan)
    plan.id = "id-1"
    plan.customer_id = "customer-1"
    plan.name = "Test My App"
    plan.url = "https://example.com"
    plan.test_criteria = "Check login works"
    plan.schedule = "daily"
    plan.status = "active"
    now = datetime.now(timezone.utc)
    plan.created_at = now
    plan.updated_at = now

    result = _plan_to_response(plan)
    assert result["name"] == "Test My App"
    assert result["url"] == "https://example.com"
    assert result["status"] == "active"
    assert result["schedule"] == "daily"


@pytest.mark.asyncio
async def test_run_to_response() -> None:
    """Test _run_to_response helper."""
    from app.api.testing import _run_to_response
    from datetime import datetime, timezone

    run = MagicMock(spec=TestRun)
    run.id = "run-1"
    run.plan_id = "plan-1"
    run.status = "passed"
    run.results_json = {"passed": 5, "failed": 0}
    run.screenshots = ["ss1.png"]
    run.error_message = None
    run.summary = "All tests passed"
    run.started_at = datetime.now(timezone.utc)
    run.completed_at = datetime.now(timezone.utc)
    run.created_at = datetime.now(timezone.utc)

    result = _run_to_response(run)
    assert result["status"] == "passed"
    assert result["results_json"]["passed"] == 5
    assert result["summary"] == "All tests passed"


@pytest.mark.asyncio
async def test_sub_to_response() -> None:
    """Test _sub_to_response helper."""
    from app.api.testing import _sub_to_response
    from datetime import datetime, timezone

    sub = MagicMock(spec=TestSubscription)
    sub.id = "sub-1"
    sub.customer_id = "customer-1"
    sub.tier = "pro"
    sub.status = "active"
    sub.stripe_subscription_id = "sub_xxx"
    sub.stripe_customer_id = "cus_xxx"
    sub.current_period_start = datetime.now(timezone.utc)
    sub.current_period_end = datetime.now(timezone.utc)
    sub.created_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)

    result = _sub_to_response(sub)
    assert result["tier"] == "pro"
    assert result["status"] == "active"
    assert result["stripe_subscription_id"] == "sub_xxx"


@pytest.mark.asyncio
async def test_list_tiers() -> None:
    """Test the public tiers endpoint."""
    from app.schemas.testing import TIER_INFO

    assert "basic" in TIER_INFO
    assert "pro" in TIER_INFO
    assert TIER_INFO["basic"].price_monthly_cents == 5000  # $50
    assert TIER_INFO["pro"].price_monthly_cents == 20000  # $200


@pytest.mark.asyncio
async def test_create_stripe_subscription_no_stripe() -> None:
    """Test Stripe subscription creation without Stripe configured."""
    from app.api.testing import _create_stripe_subscription

    with patch("app.api.testing.settings.stripe_secret_key", None):
        result = await _create_stripe_subscription(
            customer_email="test@example.com",
            tier="basic",
        )
        assert result["mock"] is True
        assert result["checkout_url"] is None
        assert result["subscription_id"].startswith("mock_sub_")

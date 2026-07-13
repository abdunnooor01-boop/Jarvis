"""Pydantic schemas for SaaS testing service — plans, runs, results, and subscriptions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
#  Test Criteria & Run Schemas (Engine-focused)
# ------------------------------------------------------------------ #


class TestCriterionCreate(BaseModel):
    """A single test criterion to verify on a website."""

    criterion: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Description of what to test (e.g. 'The login button should be visible')",
    )
    test_type: str = Field(
        default="element_visibility",
        pattern=r"^(page_load|element_visibility|text_content|link_click|form_submission|screenshot)$",
        description="Type of test to perform",
    )


class TestRunCreateRequest(BaseModel):
    """Input for creating a new test run."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Website URL to test",
    )
    name: str | None = Field(
        default=None,
        max_length=200,
        description="Optional name for this test run",
    )
    criteria: list[TestCriterionCreate] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of test criteria to verify",
    )


class TestResultResponse(BaseModel):
    """A single test result within a test run."""

    id: UUID
    run_id: UUID
    step_number: int
    criterion: str
    test_type: str
    passed: bool
    detail: str | None = None
    screenshot_path: str | None = None
    duration_ms: int = 0
    created_at: str

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ #
#  Test Plan Schemas (Plan-focused)
# ------------------------------------------------------------------ #


class TestPlanCreateRequest(BaseModel):
    """Request to create a new test plan."""

    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=500)
    test_criteria: str = Field(..., min_length=1)
    schedule: str = Field("manual", pattern=r"^(manual|daily|weekly)$")


class TestPlanUpdateRequest(BaseModel):
    """Request to update an existing test plan."""

    name: str | None = Field(None, min_length=1, max_length=200)
    url: str | None = Field(None, min_length=1, max_length=500)
    test_criteria: str | None = None
    schedule: str | None = Field(None, pattern=r"^(manual|daily|weekly)$")
    status: str | None = Field(None, pattern=r"^(active|paused|archived)$")


class TestPlanResponse(BaseModel):
    """Response schema for a test plan."""

    id: UUID
    customer_id: UUID
    name: str
    url: str
    test_criteria: str
    schedule: str
    status: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TestPlanListResponse(BaseModel):
    """Paginated list of test plans."""

    items: list[TestPlanResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


# ------------------------------------------------------------------ #
#  Test Run Response Schemas
# ------------------------------------------------------------------ #


class TestRunResponse(BaseModel):
    """Test run response returned to the client (combined fields)."""

    id: UUID
    plan_id: UUID
    user_id: UUID
    url: str
    name: str | None = None
    status: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    report_path: str | None = None
    results_json: dict[str, Any] = {}
    screenshots: list[str] = []
    error_message: str | None = None
    summary: str | None = None
    results: list[TestResultResponse] = []
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TestRunListResponse(BaseModel):
    """Paginated list of test runs."""

    items: list[TestRunResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


class TestRunStatusResponse(BaseModel):
    """Lightweight status response for a test run."""

    id: UUID
    url: str
    name: str | None = None
    status: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    report_path: str | None = None
    progress: float = 0.0  # 0.0 to 1.0
    started_at: str | None = None
    completed_at: str | None = None


class TestRunActionResponse(BaseModel):
    """Response for test run lifecycle actions."""

    run_id: UUID
    status: str
    message: str


class WebhookTriggerResponse(BaseModel):
    """Response when a CI webhook triggers a test run."""

    run_id: UUID
    status: str
    message: str
    report_url: str | None = None


class WebhookPayload(BaseModel):
    """Payload received from a CI webhook (GitHub Actions, etc.)."""

    url: str | None = Field(
        default=None,
        description="URL to test (overrides the configured test URL)",
    )
    ref: str | None = Field(
        default=None,
        description="Git ref that triggered the webhook (branch, tag)",
    )
    event: str | None = Field(
        default=None,
        description="Webhook event type (push, pull_request, etc.)",
    )
    repository: str | None = Field(
        default=None,
        description="Repository name (owner/repo)",
    )
    commit_sha: str | None = Field(
        default=None,
        description="Commit SHA that triggered the webhook",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional payload fields",
    )


# ------------------------------------------------------------------ #
#  Subscription Schemas
# ------------------------------------------------------------------ #


class SubscriptionCreateRequest(BaseModel):
    """Request to create a new subscription."""

    tier: str = Field("basic", pattern=r"^(basic|pro)$")


class SubscriptionResponse(BaseModel):
    """Response schema for a subscription."""

    id: UUID
    customer_id: UUID
    tier: str
    status: str
    stripe_subscription_id: str | None = None
    stripe_customer_id: str | None = None
    current_period_start: str | None = None
    current_period_end: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ #
#  Tier Configuration
# ------------------------------------------------------------------ #


class TierInfo(BaseModel):
    """Information about a subscription tier."""

    name: str
    price_monthly_cents: int
    max_plans: int
    max_runs_per_month: int
    description: str


# Pre-defined tiers matching TESTING_TIERS config
TIER_INFO: dict[str, TierInfo] = {
    "basic": TierInfo(
        name="Basic",
        price_monthly_cents=5000,  # $50
        max_plans=3,
        max_runs_per_month=50,
        description="For individuals and small projects",
    ),
    "pro": TierInfo(
        name="Pro",
        price_monthly_cents=20000,  # $200
        max_plans=20,
        max_runs_per_month=500,
        description="For teams and production applications",
    ),
}
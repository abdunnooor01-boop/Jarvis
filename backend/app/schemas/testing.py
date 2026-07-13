"""Pydantic schemas for SaaS testing service."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
#  Test Plan Schemas
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
#  Test Run Schemas
# ------------------------------------------------------------------ #


class TestRunResponse(BaseModel):
    """Response schema for a test run."""

    id: UUID
    plan_id: UUID
    status: str
    results_json: dict[str, Any] = {}
    screenshots: list[str] = []
    error_message: str | None = None
    summary: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class TestRunListResponse(BaseModel):
    """Paginated list of test runs."""

    items: list[TestRunResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


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

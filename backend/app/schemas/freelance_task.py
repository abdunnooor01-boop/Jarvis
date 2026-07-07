"""Pydantic schemas for freelance task catalog and payment flow."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TaskTemplateResponse(BaseModel):
    """Response schema for a task template."""

    id: UUID
    name: str
    description: str
    category: str
    price_cents: int
    price_dollars: float = 0.0
    estimated_minutes: int
    required_capabilities: list[str] = []
    is_active: bool = True

    model_config = {"from_attributes": True}


class TaskTemplateListResponse(BaseModel):
    """Paginated list of task templates."""

    items: list[TaskTemplateResponse]
    total: int


class OrderCreateRequest(BaseModel):
    """Request to create a new job order.

    Either `template_id` (for a pre-defined task) or `description`
    (for a free-form request) must be provided. If both are given,
    template_id takes precedence.
    """

    template_id: UUID | None = Field(None, description="ID of the task template (omit for free-form orders)")
    customer_email: EmailStr = Field(..., description="Customer email for receipt")
    customer_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, description="Task description or free-form request (required if no template_id)")


class OrderCreateResponse(BaseModel):
    """Response after creating a job order."""

    job_id: UUID
    template_name: str | None = None
    amount_cents: int
    amount_dollars: float
    status: str
    stripe_payment_link: str | None = None
    message: str = "Order created. Complete payment to start processing."


class FreelanceJobResponse(BaseModel):
    """Response schema for a freelance job."""

    id: UUID
    template_id: UUID | None = None
    template_name: str = ""
    customer_email: str
    customer_name: str | None = None
    description: str | None = None
    status: str
    amount_cents: int
    amount_dollars: float = 0.0
    stripe_payment_link: str | None = None
    stripe_session_id: str | None = None
    result_summary: str | None = None
    result_files: dict[str, Any] = {}
    created_at: str
    paid_at: str | None = None
    completed_at: str | None = None

    model_config = {"from_attributes": True}


class FreelanceJobListResponse(BaseModel):
    """Paginated list of freelance jobs."""

    items: list[FreelanceJobResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


class StripeWebhookPayload(BaseModel):
    """Raw Stripe webhook event payload."""

    type: str
    data: dict[str, Any]
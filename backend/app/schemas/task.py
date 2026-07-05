"""Pydantic schemas for task planning and execution."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStepResponse(BaseModel):
    """Schema for a single task step in responses."""

    id: UUID
    step_order: int
    tool_name: str
    tool_params: dict
    description: str
    status: str
    result: dict | None = None
    error: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskPlanResponse(BaseModel):
    """Schema for a complete task plan response."""

    id: UUID
    goal: str
    title: str | None = None
    status: str
    error_mode: str = "abort"
    max_retries: int = 2
    total_steps: int
    completed_steps: int = 0
    failed_steps: int = 0
    steps: list[TaskStepResponse] = []
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CreatePlanRequest(BaseModel):
    """Request to create a task plan from a goal."""

    goal: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The goal or request to break down into steps",
    )
    error_mode: str = Field(
        default="abort",
        description="abort | skip | retry — behaviour on step failure",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Max retries per step on failure",
    )


class ExecutePlanResponse(BaseModel):
    """Response when starting plan execution."""

    plan_id: UUID
    status: str
    message: str


class TaskListResponse(BaseModel):
    """Paginated list of task plans."""

    items: list[TaskPlanResponse]
    total: int
    page: int
    page_size: int


class ActionResponse(BaseModel):
    """Response to a pause/resume/cancel action."""

    plan_id: UUID
    status: str
    message: str

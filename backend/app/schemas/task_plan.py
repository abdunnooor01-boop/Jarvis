"""Pydantic schemas for task plan and task step data."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStepCreate(BaseModel):
    """Input for creating a single task step within a plan."""

    step_number: int = Field(..., ge=1)
    description: str = Field(..., min_length=1, max_length=500)
    tool_name: str = Field(..., min_length=1)
    tool_params: dict[str, Any] = Field(default_factory=dict)


class TaskPlanCreate(BaseModel):
    """Input for creating a new task plan."""

    goal: str = Field(..., min_length=1, description="High-level user goal to accomplish")


class TaskStepResponse(BaseModel):
    """Task step response returned to the client."""

    id: UUID
    plan_id: UUID
    step_number: int
    description: str
    tool_name: str
    tool_params: dict[str, Any] = {}
    status: str
    result: str | None = None
    error: str | None = None
    retry_count: int = 0
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TaskPlanResponse(BaseModel):
    """Task plan response returned to the client."""

    id: UUID
    user_id: UUID
    goal: str
    status: str
    steps: list[TaskStepResponse] = []
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TaskPlanListResponse(BaseModel):
    """Paginated list of task plans."""

    items: list[TaskPlanResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


class PlanGenerationRequest(BaseModel):
    """Request to trigger LLM-based plan generation from a goal."""

    goal: str = Field(..., min_length=1)


class PlanGenerationResponse(BaseModel):
    """Response after generating a plan from a goal."""

    plan: TaskPlanResponse
    message: str = "Plan generated successfully"
"""Pydantic schemas for the freelance job system."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class FreelanceJobCreate(BaseModel):
    """Input for creating a new freelance job."""

    title: str = Field(..., min_length=1, max_length=200, description="Job title.")
    task_type: str = Field(
        ...,
        description=(
            "Type of job: 'app_testing', 'copywriting', 'web_research', "
            "'data_entry', or 'file_processing'."
        ),
    )
    description: str = Field(..., min_length=1, description="Detailed job description.")
    input_data: dict | None = Field(
        default_factory=dict,
        description="Job-specific input parameters (e.g., URL, topic, file path).",
    )
    price: float | None = Field(None, ge=0, description="Price paid for the job.")


class FreelanceJobUpdate(BaseModel):
    """Input for updating a freelance job's status."""

    status: str = Field(..., description="New status for the job.")


class FreelanceJobResponse(BaseModel):
    """Freelance job response returned to the client."""

    id: UUID
    user_id: UUID
    title: str
    task_type: str
    description: str
    input_data: dict = {}
    status: str
    price: float | None = None
    payment_id: str | None = None
    plan_id: UUID | None = None
    result_summary: str | None = None
    result_files: list[str] = []
    deliverable_path: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    delivered_at: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class FreelanceJobListResponse(BaseModel):
    """Paginated list of freelance jobs."""

    items: list[FreelanceJobResponse]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1

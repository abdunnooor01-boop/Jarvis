"""Freelance API routes — job management and execution endpoints."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.freelance_job import FreelanceJob
from app.models.user import User
from app.schemas.freelance import (
    FreelanceJobCreate,
    FreelanceJobListResponse,
    FreelanceJobResponse,
    FreelanceJobUpdate,
)
from app.services.freelance_delivery import deliver_results
from app.services.freelance_executor import FreelanceExecutionEngine

router = APIRouter(prefix="/api/v1/freelance", tags=["freelance"])

# Background execution engine (singleton-like)
_execution_engine = FreelanceExecutionEngine()


@router.post("/jobs", response_model=FreelanceJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: FreelanceJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobResponse:
    """Create a new freelance job.

    The job is created in 'pending' status. It will be executed once
    payment is confirmed (status updated to 'paid').
    """
    job = FreelanceJob(
        user_id=current_user.id,
        title=payload.title,
        task_type=payload.task_type,
        description=payload.description,
        input_data=payload.input_data or {},
        price=payload.price,
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    return FreelanceJobResponse.model_validate(job)


@router.get("/jobs", response_model=FreelanceJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, description="Filter by status"),
    task_type: str | None = Query(None, description="Filter by task type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobListResponse:
    """List freelance jobs for the current user with pagination and filters."""
    query = select(FreelanceJob).where(FreelanceJob.user_id == current_user.id)

    if status_filter:
        query = query.where(FreelanceJob.status == status_filter)
    if task_type:
        query = query.where(FreelanceJob.task_type == task_type)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(FreelanceJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    pages = max(1, (total + page_size - 1) // page_size)

    return FreelanceJobListResponse(
        items=[FreelanceJobResponse.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/jobs/{job_id}", response_model=FreelanceJobResponse)
async def get_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobResponse:
    """Get details of a specific freelance job."""
    result = await db.execute(
        select(FreelanceJob).where(
            FreelanceJob.id == job_id,
            FreelanceJob.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Freelance job not found",
        )

    return FreelanceJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/pay", response_model=FreelanceJobResponse)
async def confirm_payment(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobResponse:
    """Confirm payment for a freelance job and trigger execution.

    This simulates a payment confirmation. In production, this would be
    called by a payment webhook. Once payment is confirmed, the job
    transitions to 'paid' and background execution begins.
    """
    result = await db.execute(
        select(FreelanceJob).where(
            FreelanceJob.id == job_id,
            FreelanceJob.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Freelance job not found",
        )

    if job.status != "pending":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is in '{job.status}' status, cannot confirm payment",
        )

    # Mark as paid
    job.status = "paid"
    await db.commit()
    await db.refresh(job)

    # Trigger background execution
    asyncio.create_task(
        _execution_engine.execute_job(str(job.id), str(current_user.id))
    )

    return FreelanceJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/deliver", response_model=FreelanceJobResponse)
async def deliver_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobResponse:
    """Deliver the results of a completed freelance job.

    Packages all artifacts into a deliverables directory, generates
    a summary report, and marks the job as 'delivered'.
    """
    result = await db.execute(
        select(FreelanceJob).where(
            FreelanceJob.id == job_id,
            FreelanceJob.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Freelance job not found",
        )

    if job.status != "completed":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is in '{job.status}' status, cannot deliver. Must be 'completed'.",
        )

    # Deliver results
    success = await deliver_results(str(job.id), str(current_user.id))

    if not success:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deliver job results",
        )

    # Refresh and return
    await db.refresh(job)
    return FreelanceJobResponse.model_validate(job)


@router.patch("/jobs/{job_id}/status", response_model=FreelanceJobResponse)
async def update_job_status(
    job_id: UUID,
    payload: FreelanceJobUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobResponse:
    """Update the status of a freelance job (admin/internal use)."""
    result = await db.execute(
        select(FreelanceJob).where(
            FreelanceJob.id == job_id,
            FreelanceJob.user_id == current_user.id,
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Freelance job not found",
        )

    valid_statuses = {"pending", "paid", "in_progress", "completed", "failed", "delivered"}
    if payload.status not in valid_statuses:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                    f"Invalid status '{payload.status}'. Must be one of: "
                    f"{', '.join(sorted(valid_statuses))}"
                ),
        )

    job.status = payload.status
    await db.commit()
    await db.refresh(job)

    return FreelanceJobResponse.model_validate(job)

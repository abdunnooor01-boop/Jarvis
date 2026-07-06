"""Developer log viewer API — query audit logs with filtering and pagination."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/v1/dev/logs", tags=["developer"])


@router.get("")
async def list_logs(
    level: str | None = Query(None, description="Filter by event type (e.g. auth_login, tool_execute)"),
    search: str | None = Query(None, description="Search in event details"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Query recent audit log entries with filtering and pagination."""
    # Build query
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    # Apply filters
    if level:
        query = query.where(AuditLog.event_type == level)
        count_query = count_query.where(AuditLog.event_type == level)

    if search:
        query = query.where(
            AuditLog.event_type.ilike(f"%{search}%")
            | AuditLog.action.ilike(f"%{search}%")
            | AuditLog.resource.ilike(f"%{search}%")
        )
        count_query = count_query.where(
            AuditLog.event_type.ilike(f"%{search}%")
            | AuditLog.action.ilike(f"%{search}%")
            | AuditLog.resource.ilike(f"%{search}%")
        )

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    logs = result.scalars().all()

    log_list = []
    for log in logs:
        log_list.append(
            {
                "id": log.id,
                "event_type": log.event_type,
                "actor_id": log.actor_id,
                "actor_ip": log.actor_ip,
                "resource": log.resource,
                "action": log.action,
                "status": log.status,
                "details": log.details or {},
                "created_at": str(log.created_at),
            }
        )

    pages = max(1, (total + page_size - 1) // page_size)

    return {
        "items": log_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/{log_id}")
async def get_log_detail(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single audit log entry by ID."""
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    log_entry = result.scalar_one_or_none()

    if log_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log entry not found",
        )

    return {
        "id": log_entry.id,
        "event_type": log_entry.event_type,
        "actor_id": log_entry.actor_id,
        "actor_ip": log_entry.actor_ip,
        "resource": log_entry.resource,
        "action": log_entry.action,
        "status": log_entry.status,
        "details": log_entry.details or {},
        "created_at": str(log_entry.created_at),
    }
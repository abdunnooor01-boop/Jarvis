"""Cross-device sync API — sync status and device management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.conversation import Conversation
from app.models.freelance_task import FreelanceJob
from app.models.knowledge_entry import KnowledgeEntry
from app.models.memory import MemoryEntry
from app.models.message import Message
from app.models.testing import TestPlan, TestRun
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sync"])


@router.get("/sync/status")
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get sync status — counts of all user data across devices.

    Returns the current state of the user's data so the mobile app
    knows what to sync. Includes conversation counts, memory entries,
    test plans, knowledge items, and notification preferences.
    """
    # Update last_active_at
    current_user.last_active_at = datetime.now(UTC)
    await db.commit()

    # Gather counts in parallel
    conversation_count = await _count(db, Conversation, Conversation.user_id == current_user.id)
    message_count = await _count(
        db, Message,
        Message.conversation_id.in_(
            select(Conversation.id).where(Conversation.user_id == current_user.id)
        ),
    )
    memory_count = await _count(db, MemoryEntry, MemoryEntry.user_id == current_user.id)
    test_plan_count = await _count(db, TestPlan, TestPlan.customer_id == current_user.id)
    test_run_count = await _count(
        db, TestRun,
        TestRun.plan_id.in_(
            select(TestPlan.id).where(TestPlan.customer_id == current_user.id)
        ),
    )
    freelance_job_count = await _count(
        db, FreelanceJob, FreelanceJob.customer_email == current_user.email
    )
    knowledge_entry_count = await _count(db, KnowledgeEntry, KnowledgeEntry.is_read == False)

    # Count devices and check preferences from notification tables (if they exist)
    device_count = 0
    has_prefs = False
    try:
        result = await db.execute(
            text("SELECT COUNT(*) FROM device_tokens WHERE user_id = :uid AND is_active = true"),
            {"uid": current_user.id},
        )
        row = result.scalar()
        device_count = row or 0
    except Exception:
        logger.debug("device_tokens table not available yet", user_id=str(current_user.id))

    try:
        result = await db.execute(
            text("SELECT COUNT(*) FROM notification_preferences WHERE user_id = :uid"),
            {"uid": current_user.id},
        )
        has_prefs = (result.scalar() or 0) > 0
    except Exception:
        logger.debug("notification_preferences table not available yet", user_id=str(current_user.id))

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "last_active_at": (
            current_user.last_active_at.isoformat()
            if current_user.last_active_at
            else None
        ),
        "data_summary": {
            "conversations": conversation_count,
            "messages": message_count,
            "memories": memory_count,
            "test_plans": test_plan_count,
            "test_runs": test_run_count,
            "freelance_jobs": freelance_job_count,
            "unread_knowledge_entries": knowledge_entry_count,
            "registered_devices": device_count,
            "has_notification_preferences": has_prefs,
        },
        "api_version": "v1",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/devices")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List all connected devices for the current user."""
    # Update last_active_at
    current_user.last_active_at = datetime.now(UTC)
    await db.commit()

    try:
        result = await db.execute(
            text("""
                SELECT id, platform, device_name, updated_at, created_at
                FROM device_tokens
                WHERE user_id = :uid AND is_active = true
                ORDER BY updated_at DESC
            """),
            {"uid": current_user.id},
        )
        rows = result.all()
        devices = [
            {
                "id": str(row[0]),
                "platform": row[1],
                "device_name": row[2] or "Unknown",
                "last_active_at": row[3].isoformat() if row[3] else None,
                "registered_at": row[4].isoformat() if row[4] else None,
            }
            for row in rows
        ]
    except Exception:
        logger.debug("device_tokens table not available yet", user_id=str(current_user.id))
        devices = []

    return {
        "devices": devices,
        "total": len(devices),
    }


async def _count(db: AsyncSession, model, where_clause) -> int:
    """Count rows matching a where clause."""
    result = await db.execute(
        select(func.count()).select_from(model).where(where_clause)
    )
    return result.scalar() or 0
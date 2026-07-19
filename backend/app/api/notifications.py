"""Push Notification API — device registration, preferences, and sending."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.notification import DeviceToken, NotificationEvent, NotificationPreference
from app.models.user import User
from app.schemas.notification import (
    DeviceTokenListResponse,
    DeviceTokenRegisterRequest,
    DeviceTokenResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    SendNotificationRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _token_to_response(token: DeviceToken) -> dict[str, Any]:
    """Convert a DeviceToken ORM object to a response dict."""
    return {
        "id": token.id,
        "token": token.token,
        "platform": token.platform,
        "device_name": token.device_name,
        "is_active": token.is_active,
        "created_at": token.created_at.isoformat(),
        "updated_at": token.updated_at.isoformat(),
    }


def _prefs_to_response(prefs: NotificationPreference) -> dict[str, Any]:
    """Convert NotificationPreference ORM to response dict."""
    return {
        "test_run_completed": prefs.test_run_completed,
        "knowledge_digest_ready": prefs.knowledge_digest_ready,
        "freelance_task_assigned": prefs.freelance_task_assigned,
        "new_message": prefs.new_message,
    }


# ------------------------------------------------------------------ #
#  Device Token Endpoints
# ------------------------------------------------------------------ #


@router.post("/register", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_device_token(
    request: DeviceTokenRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Register a device token for push notifications."""
    # Check if token already exists
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.token == request.token)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing token (re-activate if inactive)
        existing.is_active = True
        existing.platform = request.platform
        if request.device_name:
            existing.device_name = request.device_name
        await db.commit()
        await db.refresh(existing)
        logger.info(
            "Device token re-registered",
            user_id=str(current_user.id),
            platform=request.platform,
        )
        return _token_to_response(existing)

    # Create new token
    token = DeviceToken(
        user_id=current_user.id,
        token=request.token,
        platform=request.platform,
        device_name=request.device_name,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    logger.info(
        "Device token registered",
        user_id=str(current_user.id),
        platform=request.platform,
    )
    return _token_to_response(token)


@router.get("/devices", response_model=DeviceTokenListResponse)
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List all registered devices for the current user."""
    result = await db.execute(
        select(DeviceToken)
        .where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.is_active == True,
        )
        .order_by(DeviceToken.created_at.desc())
    )
    tokens = result.scalars().all()

    return {
        "devices": [_token_to_response(t) for t in tokens],
        "total": len(tokens),
    }


@router.delete("/devices/{token_id}", status_code=status.HTTP_200_OK)
async def unregister_device(
    token_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Unregister a device token."""
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.id == token_id,
            DeviceToken.user_id == current_user.id,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found",
        )

    token.is_active = False
    await db.commit()
    logger.info(
        "Device token unregistered",
        user_id=str(current_user.id),
        token_id=str(token_id),
    )
    return {"status": "ok", "message": "Device token unregistered"}


# ------------------------------------------------------------------ #
#  Notification Preferences Endpoints
# ------------------------------------------------------------------ #


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Return defaults
        return {
            "test_run_completed": True,
            "knowledge_digest_ready": True,
            "freelance_task_assigned": True,
            "new_message": True,
        }

    return _prefs_to_response(prefs)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    request: NotificationPreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Update notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create with defaults
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    # Apply updates
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)

    logger.info(
        "Notification preferences updated",
        user_id=str(current_user.id),
    )
    return _prefs_to_response(prefs)


# ------------------------------------------------------------------ #
#  Send Notification (internal)
# ------------------------------------------------------------------ #


@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
async def send_notification(
    request: SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Send a push notification to all devices.

    This is an internal endpoint used by other services to trigger
    notifications. Checks user preferences before sending.
    """
    # Check if user has notifications enabled for this event type
    prefs_result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == request.user_id
        )
    )
    prefs = prefs_result.scalar_one_or_none()

    if prefs:
        enabled = getattr(prefs, request.event_type, True)
        if not enabled:
            logger.info(
                "Notification suppressed by user preference",
                user_id=request.user_id,
                event_type=request.event_type,
            )
            return {"status": "suppressed", "reason": "user preference"}

    # Get all active device tokens for the user
    tokens_result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == request.user_id,
            DeviceToken.is_active == True,
        )
    )
    tokens = tokens_result.scalars().all()

    if not tokens:
        logger.info(
            "No devices registered for push notification",
            user_id=request.user_id,
        )
        return {"status": "skipped", "reason": "no devices"}

    # Send via FCM
    from app.services.fcm import get_fcm_service

    fcm = get_fcm_service()
    token_list = [t.token for t in tokens]
    data = {
        "event_type": request.event_type,
        **(request.data or {}),
    }

    result = await fcm.send_multicast(
        tokens=token_list,
        title=request.title,
        body=request.body,
        data=data,
    )

    # Log the notification event
    event = NotificationEvent(
        user_id=request.user_id,
        event_type=request.event_type,
        title=request.title,
        body=request.body,
        data={"device_count": len(tokens), "send_result": result},
    )
    db.add(event)
    await db.commit()

    logger.info(
        "Push notification sent",
        user_id=request.user_id,
        event_type=request.event_type,
        devices=len(tokens),
        sent=result.get("success_count", 0),
    )

    return {
        "status": "sent",
        "devices": len(tokens),
        "success_count": result.get("success_count", 0),
        "failure_count": result.get("failure_count", 0),
    }
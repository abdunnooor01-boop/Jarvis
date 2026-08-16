"""Pydantic schemas for push notifications."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class DeviceTokenRegisterRequest(BaseModel):
    """Request to register a device token for push notifications."""

    token: str = Field(..., min_length=1, max_length=500)
    platform: str = Field("unknown", pattern=r"^(ios|android|web|desktop|unknown)$")
    device_name: str | None = Field(None, max_length=200)


class DeviceTokenResponse(BaseModel):
    """Response schema for a device token."""

    id: UUID
    token: str
    platform: str
    device_name: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class DeviceTokenListResponse(BaseModel):
    """List of registered device tokens."""

    devices: list[DeviceTokenResponse]
    total: int


class NotificationPreferencesResponse(BaseModel):
    """Response schema for notification preferences."""

    test_run_completed: bool = True
    knowledge_digest_ready: bool = True
    freelance_task_assigned: bool = True
    new_message: bool = True

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdateRequest(BaseModel):
    """Request to update notification preferences."""

    test_run_completed: bool | None = None
    knowledge_digest_ready: bool | None = None
    freelance_task_assigned: bool | None = None
    new_message: bool | None = None


class SendNotificationRequest(BaseModel):
    """Request to send a notification (for internal use)."""

    user_id: str
    event_type: str = Field(..., pattern=r"^(test_run_completed|knowledge_digest_ready|freelance_task_assigned|new_message)$")
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    data: dict | None = None
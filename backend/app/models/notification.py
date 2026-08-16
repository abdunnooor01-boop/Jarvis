"""Push notification models — device tokens and notification preferences."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeviceToken(Base):
    """A registered device token for push notifications.

    Stores FCM (Firebase Cloud Messaging) tokens per user per device.
    Supports multiple devices per user (phone, tablet, laptop).
    """

    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )
    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",  # ios, android, web, desktop
    )
    device_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceToken(id={self.id}, user_id={self.user_id}, "
            f"platform={self.platform!r})>"
        )


class NotificationPreference(Base):
    """Per-user notification preferences.

    Controls which event types trigger push notifications.
    Defaults to all enabled on creation.
    """

    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        unique=True,
        index=True,
    )
    # Event type toggles (all default True)
    test_run_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    knowledge_digest_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    freelance_task_assigned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    new_message: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreference(id={self.id}, user_id={self.user_id})>"
        )


class NotificationEvent(Base):
    """A log of sent notifications (for audit and history)."""

    __tablename__ = "notification_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationEvent(id={self.id}, type={self.event_type!r}, "
            f"title={self.title!r})>"
        )
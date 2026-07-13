"""Tests for the Push Notification API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.notification import DeviceToken, NotificationPreference


@pytest.mark.asyncio
async def test_token_to_response() -> None:
    """Test _token_to_response helper."""
    from app.api.notifications import _token_to_response
    from datetime import datetime, timezone

    token = MagicMock(spec=DeviceToken)
    token.id = "token-1"
    token.token = "fcm-token-abc123"
    token.platform = "ios"
    token.device_name = "iPhone 15"
    token.is_active = True
    now = datetime.now(timezone.utc)
    token.created_at = now
    token.updated_at = now

    result = _token_to_response(token)
    assert result["token"] == "fcm-token-abc123"
    assert result["platform"] == "ios"
    assert result["device_name"] == "iPhone 15"
    assert result["is_active"] is True


@pytest.mark.asyncio
async def test_prefs_to_response() -> None:
    """Test _prefs_to_response helper."""
    from app.api.notifications import _prefs_to_response

    prefs = MagicMock(spec=NotificationPreference)
    prefs.test_run_completed = True
    prefs.knowledge_digest_ready = False
    prefs.freelance_task_assigned = True
    prefs.new_message = True

    result = _prefs_to_response(prefs)
    assert result["test_run_completed"] is True
    assert result["knowledge_digest_ready"] is False
    assert result["freelance_task_assigned"] is True


@pytest.mark.asyncio
async def test_fcm_service_not_configured() -> None:
    """Test FCMService when Firebase is not configured."""
    from app.services.fcm import FCMService

    with patch("app.services.fcm.settings.firebase_credentials_path", None):
        service = FCMService()
        ok = await service.initialize()
        assert ok is False

        result = await service.send_push(
            token="test-token",
            title="Test",
            body="Test body",
        )
        assert result is False

        multicast = await service.send_multicast(
            tokens=["test-token"],
            title="Test",
            body="Test body",
        )
        assert multicast["success_count"] == 0
        assert multicast["failure_count"] == 1


@pytest.mark.asyncio
async def test_fcm_send_push_success() -> None:
    """Test FCMService.send_push success path."""
    from app.services.fcm import FCMService
    import firebase_admin.messaging

    service = FCMService()
    service._initialized = True

    with patch.object(firebase_admin.messaging, "send", return_value="test-response"):
        result = await service.send_push(
            token="test-token",
            title="Test",
            body="Test body",
            data={"key": "value"},
        )
        assert result is True


@pytest.mark.asyncio
async def test_fcm_send_multicast_success() -> None:
    """Test FCMService.send_multicast success path."""
    from app.services.fcm import FCMService
    import firebase_admin.messaging

    service = FCMService()
    service._initialized = True

    mock_response = MagicMock()
    mock_response.success_count = 2
    mock_response.failure_count = 0

    with patch.object(firebase_admin.messaging, "send_each", return_value=mock_response):
        result = await service.send_multicast(
            tokens=["token-1", "token-2"],
            title="Test",
            body="Test body",
        )
        assert result["success_count"] == 2
        assert result["failure_count"] == 0


@pytest.mark.asyncio
async def test_shared_types_exist() -> None:
    """Test that the shared notification types file exists."""
    import os

    path = "/home/team/shared/jarvis-repo/packages/shared/src/notification.ts"
    assert os.path.exists(path), f"Shared types file not found at {path}"
    content = open(path).read()
    assert "NotificationEventType" in content
    assert "NotificationPayload" in content
    assert "DeviceToken" in content
    assert "NotificationPreferences" in content
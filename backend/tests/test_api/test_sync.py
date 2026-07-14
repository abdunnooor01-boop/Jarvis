"""Tests for the cross-device sync API."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User


@pytest.mark.asyncio
async def test_sync_status_returns_data_summary() -> None:
    """Test that sync status endpoint returns expected structure."""
    from app.api.sync import get_sync_status

    mock_user = MagicMock(spec=User)
    mock_user.id = "user-1"
    mock_user.email = "test@example.com"
    mock_user.display_name = "Test User"
    mock_user.last_active_at = datetime.now(UTC)

    mock_db = AsyncMock()

    # Make _count return varying counts
    with patch("app.api.sync._count") as mock_count:
        mock_count.side_effect = [3, 15, 8, 2, 5, 1, 4]  # conversations, messages, memories, test_plans, test_runs, freelance, knowledge

        # Mock the device_tokens raw query (Exception to simulate table not existing)
        mock_db.execute.side_effect = [Exception("table not found"), Exception("table not found")]

        result = await get_sync_status(db=mock_db, current_user=mock_user)
        assert result["user_id"] == "user-1"
        assert result["email"] == "test@example.com"
        assert result["display_name"] == "Test User"
        assert result["data_summary"]["conversations"] == 3
        assert result["data_summary"]["messages"] == 15
        assert result["data_summary"]["memories"] == 8
        assert result["data_summary"]["test_plans"] == 2
        assert result["data_summary"]["test_runs"] == 5
        assert result["data_summary"]["freelance_jobs"] == 1
        assert result["data_summary"]["unread_knowledge_entries"] == 4
        assert result["data_summary"]["registered_devices"] == 0
        assert result["data_summary"]["has_notification_preferences"] is False
        assert result["api_version"] == "v1"
        assert "timestamp" in result


@pytest.mark.asyncio
async def test_sync_status_updates_last_active() -> None:
    """Test that calling sync status updates last_active_at."""
    from app.api.sync import get_sync_status

    mock_user = MagicMock(spec=User)
    mock_user.id = "user-2"
    mock_user.email = "user@example.com"
    mock_user.display_name = "User"
    mock_user.last_active_at = None

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [Exception("table not found"), Exception("table not found")]

    with patch("app.api.sync._count") as mock_count:
        mock_count.side_effect = [0, 0, 0, 0, 0, 0, 0]
        result = await get_sync_status(db=mock_db, current_user=mock_user)
        assert mock_user.last_active_at is not None
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_devices_returns_device_list() -> None:
    """Test that devices endpoint returns device list."""
    from app.api.sync import list_devices

    mock_user = MagicMock(spec=User)
    mock_user.id = "user-3"
    mock_user.last_active_at = None

    mock_db = AsyncMock()

    # Mock device token query result
    mock_row = ("device-1", "ios", "iPhone 15", datetime.now(UTC), datetime.now(UTC))

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_db.execute.return_value = mock_result

    result = await list_devices(db=mock_db, current_user=mock_user)
    assert result["total"] == 1
    assert result["devices"][0]["id"] == "device-1"
    assert result["devices"][0]["platform"] == "ios"
    assert result["devices"][0]["device_name"] == "iPhone 15"


@pytest.mark.asyncio
async def test_devices_empty_list() -> None:
    """Test that devices endpoint returns empty list when no devices."""
    from app.api.sync import list_devices

    mock_user = MagicMock(spec=User)
    mock_user.id = "user-4"
    mock_user.last_active_at = None

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await list_devices(db=mock_db, current_user=mock_user)
    assert result["total"] == 0
    assert result["devices"] == []


@pytest.mark.asyncio
async def test_devices_handles_missing_table() -> None:
    """Test that devices endpoint falls back gracefully when table missing."""
    from app.api.sync import list_devices

    mock_user = MagicMock(spec=User)
    mock_user.id = "user-5"
    mock_user.last_active_at = None

    mock_db = AsyncMock()
    mock_db.execute.side_effect = Exception("table not found")

    result = await list_devices(db=mock_db, current_user=mock_user)
    assert result["total"] == 0
    assert result["devices"] == []


@pytest.mark.asyncio
async def test_user_has_last_active_at_field() -> None:
    """Test that User model has the last_active_at field."""
    from app.models.user import User
    assert hasattr(User, "last_active_at")
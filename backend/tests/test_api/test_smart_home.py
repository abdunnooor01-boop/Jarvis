"""Tests for the smart home plugin framework — model, service, and API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.smart_home import (
    DEVICE_TYPE_SCHEMAS,
    DeviceType,
    SmartHomeDevice,
    get_all_capabilities,
    get_default_state,
    get_required_capabilities,
)


@pytest.mark.asyncio
async def test_device_type_enum() -> None:
    """Test that DeviceType enum has expected values."""
    assert DeviceType.LIGHT == "light"
    assert DeviceType.SWITCH == "switch"
    assert DeviceType.SENSOR == "sensor"
    assert DeviceType.THERMOSTAT == "thermostat"
    assert DeviceType.LOCK == "lock"
    assert DeviceType.CAMERA == "camera"
    assert DeviceType.COVER == "cover"
    assert DeviceType.SPEAKER == "speaker"


@pytest.mark.asyncio
async def test_device_type_schemas_exist() -> None:
    """Test that all device types have schemas defined."""
    assert "light" in DEVICE_TYPE_SCHEMAS
    assert "switch" in DEVICE_TYPE_SCHEMAS
    assert "sensor" in DEVICE_TYPE_SCHEMAS
    assert "thermostat" in DEVICE_TYPE_SCHEMAS
    assert "lock" in DEVICE_TYPE_SCHEMAS
    assert "camera" in DEVICE_TYPE_SCHEMAS
    assert "cover" in DEVICE_TYPE_SCHEMAS
    assert "speaker" in DEVICE_TYPE_SCHEMAS


@pytest.mark.asyncio
async def test_get_default_state() -> None:
    """Test that get_default_state returns correct defaults."""
    light_state = get_default_state("light")
    assert "on" in light_state
    assert light_state["on"] is False
    assert light_state["brightness"] == 255

    lock_state = get_default_state("lock")
    assert lock_state["locked"] is True

    cover_state = get_default_state("cover")
    assert cover_state["position"] == 0
    assert cover_state["is_closed"] is True


@pytest.mark.asyncio
async def test_get_required_capabilities() -> None:
    """Test that required capabilities are correctly defined."""
    light_caps = get_required_capabilities("light")
    assert "on_off" in light_caps

    lock_caps = get_required_capabilities("lock")
    assert "lock_unlock" in lock_caps


@pytest.mark.asyncio
async def test_get_all_capabilities() -> None:
    """Test that all capabilities includes required + optional."""
    light_caps = get_all_capabilities("light")
    assert "on_off" in light_caps
    assert "brightness" in light_caps


@pytest.mark.asyncio
async def test_smart_home_device_model() -> None:
    """Test that SmartHomeDevice model has expected fields."""
    assert hasattr(SmartHomeDevice, "id")
    assert hasattr(SmartHomeDevice, "user_id")
    assert hasattr(SmartHomeDevice, "external_id")
    assert hasattr(SmartHomeDevice, "integration")
    assert hasattr(SmartHomeDevice, "device_type")
    assert hasattr(SmartHomeDevice, "name")
    assert hasattr(SmartHomeDevice, "room")
    assert hasattr(SmartHomeDevice, "manufacturer")
    assert hasattr(SmartHomeDevice, "model")
    assert hasattr(SmartHomeDevice, "capabilities")
    assert hasattr(SmartHomeDevice, "state")
    assert hasattr(SmartHomeDevice, "is_online")
    assert hasattr(SmartHomeDevice, "is_favorite")


@pytest.mark.asyncio
async def test_register_device_creates_new() -> None:
    """Test registering a new device via the service."""
    from app.services.smart_home import SmartHomeService

    service = SmartHomeService()
    mock_db = AsyncMock()

    # Mock select to return no existing device
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    device = await service.register_device(
        db=mock_db,
        user_id="user-1",
        external_id="light.living_room",
        integration="home_assistant",
        device_type="light",
        name="Living Room Light",
        room="Living Room",
        manufacturer="Philips",
        model="Hue White",
    )

    assert device is not None
    assert device.name == "Living Room Light"
    assert device.device_type == "light"
    assert device.room == "Living Room"


@pytest.mark.asyncio
async def test_smart_home_plugin_abc() -> None:
    """Test that the SmartHomePlugin ABC defines expected methods."""
    from app.services.smart_home_plugin import SmartHomePlugin

    # Check that it's abstract
    assert SmartHomePlugin.__abstractmethods__ is not None
    assert "name" in SmartHomePlugin.__abstractmethods__
    assert "discover_devices" in SmartHomePlugin.__abstractmethods__
    assert "sync_state" in SmartHomePlugin.__abstractmethods__
    assert "execute_command" in SmartHomePlugin.__abstractmethods__


@pytest.mark.asyncio
async def test_smart_home_api_router() -> None:
    """Test that the smart home API router has the expected routes."""
    from app.api.smart_home import router

    routes = [(r.path, list(r.methods)) for r in router.routes]
    paths = [r[0] for r in routes]

    assert "/devices" in paths  # GET /api/v1/smart-home/devices
    assert "/devices/{device_id}" in paths  # GET /api/v1/smart-home/devices/{id}
    assert "/devices/{device_id}/state" in paths  # PATCH
    assert "/rooms" in paths  # GET /api/v1/smart-home/rooms
    assert "/types" in paths  # GET /api/v1/smart-home/types


@pytest.mark.asyncio
async def test_plugin_registry() -> None:
    """Test the plugin registry functions."""
    from app.services.smart_home_plugin import (
        get_all_plugins,
        get_plugin,
        get_plugin_names,
        register_plugin,
    )
    from unittest.mock import MagicMock

    # Clear registry
    import app.services.smart_home_plugin as plugin_mod
    plugin_mod._plugins = {}

    mock_plugin = MagicMock()
    mock_plugin.name = "test_plugin"

    register_plugin(mock_plugin)
    assert get_plugin("test_plugin") is mock_plugin
    assert "test_plugin" in get_plugin_names()
    assert len(get_all_plugins()) == 1

    # Clean up
    plugin_mod._plugins = {}
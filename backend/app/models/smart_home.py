"""Smart Home ORM models and type definitions.

Defines the abstract device model that all smart home integrations
(Home Assistant, Hubitat, etc.) map to.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeviceType(str, Enum):
    """Supported smart home device types."""

    LIGHT = "light"
    SWITCH = "switch"
    SENSOR = "sensor"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    COVER = "cover"
    SPEAKER = "speaker"
    FAN = "fan"
    VACUUM = "vacuum"
    UNKNOWN = "unknown"


class DeviceCapability(str, Enum):
    """Capabilities a device may support."""

    ON_OFF = "on_off"
    BRIGHTNESS = "brightness"
    COLOR_TEMP = "color_temp"
    COLOR_RGB = "color_rgb"
    TEMPERATURE_SET = "temperature_set"
    TARGET_TEMP = "target_temp"
    LOCK_UNLOCK = "lock_unlock"
    OPEN_CLOSE = "open_close"
    POSITION = "position"
    VOLUME = "volume"
    MOTION = "motion"
    PRESENCE = "presence"
    HUMIDITY = "humidity"
    ILLUMINANCE = "illuminance"
    BATTERY = "battery"
    ENERGY = "energy"


class SmartHomeDevice(Base):
    """A registered smart home device.

    Stores the canonical device state that all integrations sync to.
    Each device has a type, room assignment, capabilities, and state.
    """

    __tablename__ = "smart_home_devices"

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
    external_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="ID from the integration (e.g. Home Assistant entity_id)",
    )
    integration: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Integration name: home_assistant, hubitat, matter, etc.",
    )
    device_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    room: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    manufacturer: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    capabilities: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="List of DeviceCapability strings this device supports",
    )
    state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Current device state (varies by type, e.g. {on: true, brightness: 80})",
    )
    is_online: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether the device is currently reachable",
    )
    is_favorite: Mapped[bool] = mapped_column(
        default=False,
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
            f"<SmartHomeDevice(id={self.id}, type={self.device_type!r}, "
            f"name={self.name!r}, room={self.room!r})>"
        )


# ------------------------------------------------------------------
# Device type schemas — what state attributes each type supports
# ------------------------------------------------------------------

DEVICE_TYPE_SCHEMAS: dict[str, dict[str, Any]] = {
    "light": {
        "attributes": {
            "on": {"type": "boolean", "default": False},
            "brightness": {"type": "integer", "min": 0, "max": 255, "default": 255},
            "color_temp": {"type": "integer", "min": 153, "max": 500, "default": None},
            "rgb_color": {"type": "array", "items": {"type": "integer", "min": 0, "max": 255}, "default": None},
        },
        "required_capabilities": [DeviceCapability.ON_OFF],
        "optional_capabilities": [DeviceCapability.BRIGHTNESS, DeviceCapability.COLOR_TEMP, DeviceCapability.COLOR_RGB],
    },
    "switch": {
        "attributes": {
            "on": {"type": "boolean", "default": False},
        },
        "required_capabilities": [DeviceCapability.ON_OFF],
        "optional_capabilities": [],
    },
    "sensor": {
        "attributes": {
            "state": {"type": "string", "default": "unknown"},
            "unit_of_measurement": {"type": "string", "default": None},
            "value": {"type": "number", "default": None},
        },
        "required_capabilities": [],
        "optional_capabilities": [DeviceCapability.MOTION, DeviceCapability.PRESENCE, DeviceCapability.HUMIDITY, DeviceCapability.ILLUMINANCE, DeviceCapability.BATTERY, DeviceCapability.TEMPERATURE_SET],
    },
    "thermostat": {
        "attributes": {
            "on": {"type": "boolean", "default": False},
            "target_temp": {"type": "number", "default": 21.0},
            "current_temp": {"type": "number", "default": None},
            "hvac_mode": {"type": "string", "enum": ["off", "heat", "cool", "auto", "dry", "fan_only"], "default": "off"},
            "humidity": {"type": "integer", "default": None},
        },
        "required_capabilities": [DeviceCapability.ON_OFF, DeviceCapability.TARGET_TEMP],
        "optional_capabilities": [DeviceCapability.TEMPERATURE_SET, DeviceCapability.HUMIDITY],
    },
    "lock": {
        "attributes": {
            "locked": {"type": "boolean", "default": True},
        },
        "required_capabilities": [DeviceCapability.LOCK_UNLOCK],
        "optional_capabilities": [DeviceCapability.BATTERY],
    },
    "camera": {
        "attributes": {
            "on": {"type": "boolean", "default": False},
            "stream_url": {"type": "string", "default": None},
            "motion_detected": {"type": "boolean", "default": False},
        },
        "required_capabilities": [DeviceCapability.ON_OFF],
        "optional_capabilities": [DeviceCapability.MOTION],
    },
    "cover": {
        "attributes": {
            "position": {"type": "integer", "min": 0, "max": 100, "default": 0},
            "is_closed": {"type": "boolean", "default": True},
        },
        "required_capabilities": [DeviceCapability.OPEN_CLOSE, DeviceCapability.POSITION],
        "optional_capabilities": [],
    },
    "speaker": {
        "attributes": {
            "on": {"type": "boolean", "default": False},
            "volume": {"type": "integer", "min": 0, "max": 100, "default": 50},
            "source": {"type": "string", "default": None},
        },
        "required_capabilities": [DeviceCapability.ON_OFF, DeviceCapability.VOLUME],
        "optional_capabilities": [],
    },
}


def get_default_state(device_type: str) -> dict[str, Any]:
    """Get the default state for a given device type."""
    schema = DEVICE_TYPE_SCHEMAS.get(device_type, {})
    attributes = schema.get("attributes", {})
    return {
        attr: info["default"]
        for attr, info in attributes.items()
        if info["default"] is not None
    }


def get_required_capabilities(device_type: str) -> list[str]:
    """Get the required capabilities for a device type."""
    schema = DEVICE_TYPE_SCHEMAS.get(device_type, {})
    return [c.value for c in schema.get("required_capabilities", [])]


def get_all_capabilities(device_type: str) -> list[str]:
    """Get all capabilities (required + optional) for a device type."""
    schema = DEVICE_TYPE_SCHEMAS.get(device_type, {})
    required = [c.value for c in schema.get("required_capabilities", [])]
    optional = [c.value for c in schema.get("optional_capabilities", [])]
    return required + optional
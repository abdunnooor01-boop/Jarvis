"""Smart Home Service — device registry, discovery, and state management.

Provides the core service layer that all smart home integrations
interact with. Handles device registration, state updates, and
real-time event broadcasting via WebSocket.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws import manager as ws_manager
from app.core.logging import get_logger
from app.models.smart_home import (
    DEVICE_TYPE_SCHEMAS,
    SmartHomeDevice,
    get_all_capabilities,
    get_default_state,
)

logger = get_logger(__name__)


class SmartHomeService:
    """Manages the smart home device registry and state.

    Provides methods for registering, discovering, and updating
    devices. Broadcasts state changes via WebSocket for real-time UI.
    """

    async def register_device(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        external_id: str,
        integration: str,
        device_type: str,
        name: str,
        room: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> SmartHomeDevice:
        """Register a new device or update an existing one.

        If a device with the same external_id and integration exists,
        it updates the existing record instead of creating a duplicate.
        """
        # Check for existing device
        result = await db.execute(
            select(SmartHomeDevice).where(
                SmartHomeDevice.user_id == user_id,
                SmartHomeDevice.external_id == external_id,
                SmartHomeDevice.integration == integration,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.name = name
            existing.device_type = device_type
            existing.room = room
            existing.manufacturer = manufacturer
            existing.model = model
            existing.capabilities = get_all_capabilities(device_type)
            existing.state = state or get_default_state(device_type)
            existing.is_online = True
            await db.commit()
            await db.refresh(existing)

            logger.info(
                "Device updated",
                device_id=str(existing.id),
                name=name,
                integration=integration,
            )
            return existing

        # Create new device
        device = SmartHomeDevice(
            user_id=user_id,
            external_id=external_id,
            integration=integration,
            device_type=device_type,
            name=name,
            room=room,
            manufacturer=manufacturer,
            model=model,
            capabilities=get_all_capabilities(device_type),
            state=state or get_default_state(device_type),
            is_online=True,
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)

        logger.info(
            "Device registered",
            device_id=str(device.id),
            name=name,
            type=device_type,
            integration=integration,
        )

        # Broadcast device added event
        await self._broadcast_event(
            str(user_id),
            {
                "type": "smart_home_device_added",
                "device": self._device_to_dict(device),
            },
        )

        return device

    async def get_device(
        self,
        db: AsyncSession,
        device_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SmartHomeDevice | None:
        """Get a single device by ID."""
        result = await db.execute(
            select(SmartHomeDevice).where(
                SmartHomeDevice.id == device_id,
                SmartHomeDevice.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_devices(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        room: str | None = None,
        device_type: str | None = None,
    ) -> list[SmartHomeDevice]:
        """List devices for a user, optionally filtered by room or type."""
        query = select(SmartHomeDevice).where(
            SmartHomeDevice.user_id == user_id
        )

        if room:
            query = query.where(SmartHomeDevice.room == room)
        if device_type:
            query = query.where(SmartHomeDevice.device_type == device_type)

        query = query.order_by(SmartHomeDevice.room, SmartHomeDevice.name)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_device_state(
        self,
        db: AsyncSession,
        device_id: uuid.UUID,
        user_id: uuid.UUID,
        state_updates: dict[str, Any],
    ) -> SmartHomeDevice | None:
        """Update the state of a device.

        Merges the provided state updates into the current state.
        Broadcasts the change via WebSocket.
        """
        device = await self.get_device(db, device_id, user_id)
        if device is None:
            return None

        # Merge state updates
        current_state = dict(device.state or {})
        current_state.update(state_updates)
        device.state = current_state
        device.is_online = True

        await db.commit()
        await db.refresh(device)

        logger.info(
            "Device state updated",
            device_id=str(device.id),
            name=device.name,
            updates=state_updates,
        )

        # Broadcast state change
        await self._broadcast_event(
            str(user_id),
            {
                "type": "smart_home_state_changed",
                "device_id": str(device.id),
                "state": device.state,
            },
        )

        return device

    async def remove_device(
        self,
        db: AsyncSession,
        device_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Remove a device from the registry."""
        result = await db.execute(
            select(SmartHomeDevice).where(
                SmartHomeDevice.id == device_id,
                SmartHomeDevice.user_id == user_id,
            )
        )
        device = result.scalar_one_or_none()
        if device is None:
            return False

        await db.delete(device)
        await db.commit()

        logger.info(
            "Device removed",
            device_id=str(device_id),
            name=device.name,
        )

        await self._broadcast_event(
            str(user_id),
            {
                "type": "smart_home_device_removed",
                "device_id": str(device_id),
            },
        )

        return True

    async def get_rooms(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[str]:
        """Get a list of all rooms that have devices."""
        result = await db.execute(
            select(SmartHomeDevice.room)
            .where(
                SmartHomeDevice.user_id == user_id,
                SmartHomeDevice.room.isnot(None),
            )
            .distinct()
            .order_by(SmartHomeDevice.room)
        )
        return [row[0] for row in result.all()]

    async def get_device_types(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get device type summary with counts per type."""
        from sqlalchemy import func

        result = await db.execute(
            select(
                SmartHomeDevice.device_type,
                func.count(SmartHomeDevice.id),
            )
            .where(SmartHomeDevice.user_id == user_id)
            .group_by(SmartHomeDevice.device_type)
        )
        return [
            {"device_type": row[0], "count": row[1]}
            for row in result.all()
        ]

    async def get_supported_types(self) -> list[dict[str, Any]]:
        """Get all supported device types with their schemas."""
        return [
            {
                "device_type": dt,
                "attributes": schema.get("attributes", {}),
                "required_capabilities": schema.get("required_capabilities", []),
                "optional_capabilities": schema.get("optional_capabilities", []),
            }
            for dt, schema in DEVICE_TYPE_SCHEMAS.items()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _device_to_dict(self, device: SmartHomeDevice) -> dict[str, Any]:
        """Convert a device ORM object to a response dict."""
        return {
            "id": str(device.id),
            "external_id": device.external_id,
            "integration": device.integration,
            "device_type": device.device_type,
            "name": device.name,
            "room": device.room,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "capabilities": device.capabilities or [],
            "state": device.state or {},
            "is_online": device.is_online,
            "is_favorite": device.is_favorite,
            "created_at": device.created_at.isoformat(),
            "updated_at": device.updated_at.isoformat(),
        }

    async def _broadcast_event(self, user_id: str, event: dict[str, Any]) -> None:
        """Broadcast an event to the user's WebSocket connections."""
        try:
            await ws_manager.send_json(user_id, event)
        except Exception as e:
            logger.debug(
                "WebSocket broadcast failed (no active connection)",
                user_id=user_id,
                event_type=event.get("type"),
                error=str(e),
            )


# Singleton
_service: SmartHomeService | None = None


def get_smart_home_service() -> SmartHomeService:
    """Get or create the SmartHomeService singleton."""
    global _service
    if _service is None:
        _service = SmartHomeService()
    return _service
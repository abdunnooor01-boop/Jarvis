"""Smart Home API — device management, state control, and discovery."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.smart_home import DEVICE_TYPE_SCHEMAS, DeviceType
from app.models.user import User
from app.services.smart_home import get_smart_home_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/smart-home", tags=["smart-home"])


@router.get("/devices")
async def list_devices(
    room: str | None = Query(None, description="Filter by room name"),
    device_type: str | None = Query(None, description="Filter by device type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all smart home devices for the current user.

    Optionally filter by room or device type.
    """
    service = get_smart_home_service()
    devices = await service.list_devices(
        db=db,
        user_id=current_user.id,
        room=room,
        device_type=device_type,
    )

    return {
        "devices": [
            {
                "id": str(d.id),
                "external_id": d.external_id,
                "integration": d.integration,
                "device_type": d.device_type,
                "name": d.name,
                "room": d.room,
                "manufacturer": d.manufacturer,
                "model": d.model,
                "capabilities": d.capabilities or [],
                "state": d.state or {},
                "is_online": d.is_online,
                "is_favorite": d.is_favorite,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in devices
        ],
        "total": len(devices),
    }


@router.get("/devices/{device_id}")
async def get_device(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get details of a specific smart home device."""
    service = get_smart_home_service()
    device = await service.get_device(db=db, device_id=device_id, user_id=current_user.id)

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

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


@router.patch("/devices/{device_id}/state")
async def update_device_state(
    device_id: uuid.UUID,
    body: DeviceStateUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update the state of a smart home device.

    Merges the provided state updates into the current device state.
    Broadcasts the change via WebSocket for real-time UI updates.
    """
    service = get_smart_home_service()
    device = await service.update_device_state(
        db=db,
        device_id=device_id,
        user_id=current_user.id,
        state_updates=body.state,
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return {
        "id": str(device.id),
        "name": device.name,
        "state": device.state,
        "message": "Device state updated",
    }


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a device from the smart home registry."""
    service = get_smart_home_service()
    success = await service.remove_device(
        db=db,
        device_id=device_id,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )


@router.get("/rooms")
async def get_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a list of all rooms that have devices."""
    service = get_smart_home_service()
    rooms = await service.get_rooms(db=db, user_id=current_user.id)
    return {"rooms": rooms, "total": len(rooms)}


@router.get("/types")
async def get_device_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get device type summary with counts and supported schemas."""
    service = get_smart_home_service()
    types_summary = await service.get_device_types(db=db, user_id=current_user.id)
    supported_types = await service.get_supported_types()

    return {
        "summary": types_summary,
        "supported_types": supported_types,
    }


@router.post("/devices")
async def register_device(
    body: DeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a new smart home device."""
    service = get_smart_home_service()
    device = await service.register_device(
        db=db,
        user_id=current_user.id,
        external_id=body.external_id,
        integration=body.integration,
        device_type=body.device_type,
        name=body.name,
        room=body.room,
        manufacturer=body.manufacturer,
        model=body.model,
        state=body.state,
    )

    return {
        "id": str(device.id),
        "external_id": device.external_id,
        "integration": device.integration,
        "device_type": device.device_type,
        "name": device.name,
        "room": device.room,
        "capabilities": device.capabilities or [],
        "state": device.state or {},
        "message": "Device registered successfully",
    }


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------


from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    """Request to register a new smart home device."""

    external_id: str = Field(..., min_length=1, max_length=200)
    integration: str = Field(..., min_length=1, max_length=50)
    device_type: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=200)
    room: str | None = Field(None, max_length=100)
    manufacturer: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    state: dict[str, Any] | None = None


class DeviceStateUpdateRequest(BaseModel):
    """Request to update device state."""

    state: dict[str, Any] = Field(
        ...,
        min_length=1,
        description="State attributes to update (e.g. {'on': true, 'brightness': 80})",
    )
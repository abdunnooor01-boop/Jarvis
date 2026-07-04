"""Plugin-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.plugin_system.plugin_manifest import ToolManifest


class PluginResponse(BaseModel):
    """Plugin summary response."""

    id: UUID
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    enabled: bool
    installed_at: datetime


class PluginDetail(PluginResponse):
    """Detailed plugin response including tools and settings."""

    tools: list[ToolManifest] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)


class PluginToggle(BaseModel):
    """Toggle a plugin's enabled status."""

    enabled: bool = Field(..., description="Whether to enable or disable the plugin.")


class PluginInstall(BaseModel):
    """Install a plugin from a local path or URL."""

    path: str = Field(..., description="The local path or URL to install the plugin from.")

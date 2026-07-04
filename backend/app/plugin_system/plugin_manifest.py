"""Plugin manifest schemas and parsing logic."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolManifest(BaseModel):
    """Manifest definition for an individual tool provided by a plugin."""

    name: str = Field(..., description="The name of the tool, in snake_case.")
    description: str = Field(..., description="A description of what the tool does.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema defining the tool's expected input parameters.",
    )


class PluginManifest(BaseModel):
    """Manifest definition for a Jarvis plugin."""

    name: str = Field(..., description="The unique name of the plugin.")
    version: str = Field(..., description="The version of the plugin (e.g., 1.0.0).")
    description: str = Field(..., description="A short description of the plugin's capabilities.")
    author: str | None = Field(None, description="The author of the plugin.")
    tools: list[ToolManifest] = Field(
        default_factory=list,
        description="The list of tools provided by this plugin.",
    )

"""Developer API routes — plugin validation, tooling, and introspection.

This router provides endpoints for plugin developers to validate their
plugins before deploying them.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import traceback
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.plugin_system.plugin_manifest import PluginManifest, ToolManifest

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ValidateByPath(BaseModel):
    """Validate a plugin by filesystem path."""

    path: str = Field(
        ...,
        description="Absolute or relative path to the plugin directory.",
    )


class ToolManifestContent(BaseModel):
    """A single tool definition, as it would appear in a manifest."""

    name: str = Field(..., description="Tool name in snake_case.")
    description: str = Field(..., description="What the tool does.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool parameters.",
    )


class ManifestContent(BaseModel):
    """Inline manifest content to validate."""

    name: str = Field(..., description="Plugin name.")
    version: str = Field(..., description="Semantic version string.")
    description: str = Field(..., description="Plugin description.")
    author: str | None = Field(None, description="Plugin author.")
    tools: list[ToolManifestContent] = Field(
        default_factory=list,
        description="List of tool definitions.",
    )


class ValidateByManifest(BaseModel):
    """Validate a plugin by its manifest content."""

    manifest: ManifestContent = Field(
        ...,
        description="The plugin manifest content to validate.",
    )


class ValidationIssue(BaseModel):
    """A single validation issue (warning or error)."""

    type: str = Field(..., description="Either 'error' or 'warning'.")
    message: str = Field(..., description="Human-readable description of the issue.")
    location: str | None = Field(None, description="Where the issue was found.")


class ValidationResult(BaseModel):
    """Result of a plugin validation check."""

    valid: bool = Field(
        ...,
        description="Whether the plugin passed validation (no errors).",
    )
    name: str | None = Field(
        None,
        description="Plugin name extracted from the manifest.",
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="Validation issues (warnings and errors).",
    )
    tool_count: int = Field(
        0,
        description="Number of tools defined in the manifest.",
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _find_plugin_root(search_path: str) -> str | None:
    """Resolve *search_path* to an actual plugin directory.

    Tries the path as-is, then relative to the standard plugins directory.
    Returns ``None`` if the directory does not exist.
    """
    # Try as absolute or relative to CWD
    plugins_base = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "plugins",
        )
    )

    candidates = [
        search_path,
        os.path.join(plugins_base, search_path),
    ]

    for candidate in candidates:
        resolved = os.path.abspath(candidate)
        if os.path.isdir(resolved):
            return resolved

    return None


def _load_manifest_from_disk(plugin_dir: str) -> dict[str, Any] | None:
    """Load and parse ``plugin.yaml`` from a plugin directory."""
    yaml_path = os.path.join(plugin_dir, "plugin.yaml")
    if not os.path.isfile(yaml_path):
        return None
    try:
        with open(yaml_path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError:
        return None


def _validate_manifest_schema(
    manifest_data: dict[str, Any],
) -> list[ValidationIssue]:
    """Validate manifest fields against the PluginManifest schema."""
    issues: list[ValidationIssue] = []

    try:
        PluginManifest(**manifest_data)
    except Exception as exc:
        issues.append(
            ValidationIssue(
                type="error",
                message=f"Manifest schema validation failed: {exc}",
                location="plugin.yaml",
            )
        )

    return issues


def _validate_tool_schemas(
    manifest_data: dict[str, Any],
) -> list[ValidationIssue]:
    """Validate individual tool definitions."""
    issues: list[ValidationIssue] = []

    tools = manifest_data.get("tools", [])
    if not tools:
        issues.append(
            ValidationIssue(
                type="error",
                message="No tools defined in manifest. At least one tool is required.",
                location="plugin.yaml -> tools",
            )
        )
        return issues

    for i, tool in enumerate(tools):
        # Validate tool schema
        try:
            ToolManifest(**tool)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    type="error",
                    message=f"Tool at index {i} failed schema validation: {exc}",
                    location=f"plugin.yaml -> tools[{i}]",
                )
            )
            continue

        # Check that the tool name is snake_case
        tool_name = tool.get("name", "")
        if not tool_name or not tool_name.replace("_", "").isalnum():
            issues.append(
                ValidationIssue(
                    type="error",
                    message=(
                        f"Tool name '{tool_name}' must be in snake_case "
                        "(lowercase, underscores only)."
                    ),
                    location=f"plugin.yaml -> tools[{i}] -> name",
                )
            )

    return issues


def _validate_directory_structure(plugin_dir: str) -> list[ValidationIssue]:
    """Check that the plugin has the required directory structure."""
    issues: list[ValidationIssue] = []

    if not os.path.isfile(os.path.join(plugin_dir, "plugin.yaml")):
        issues.append(
            ValidationIssue(
                type="error",
                message="Missing plugin.yaml manifest file.",
                location=str(plugin_dir),
            )
        )

    if not os.path.isfile(os.path.join(plugin_dir, "__init__.py")):
        issues.append(
            ValidationIssue(
                type="warning",
                message="Missing __init__.py — plugin may not load correctly.",
                location=str(plugin_dir),
            )
        )

    tools_dir = os.path.join(plugin_dir, "tools")
    if not os.path.isdir(tools_dir):
        issues.append(
            ValidationIssue(
                type="error",
                message="Missing tools/ directory.",
                location=str(plugin_dir),
            )
        )

    return issues


def _validate_tool_imports(plugin_dir: str, tools: list[dict[str, Any]]) -> list[ValidationIssue]:
    """Try to import each tool class to verify it's loadable."""
    issues: list[ValidationIssue] = []

    for tool in tools:
        tool_name = tool.get("name", "unknown")
        tool_file_name = f"{tool_name}.py"
        tool_path = os.path.join(plugin_dir, "tools", tool_file_name)

        if not os.path.isfile(tool_path):
            issues.append(
                ValidationIssue(
                    type="warning",
                    message=f"Tool module '{tool_file_name}' not found. "
                            f"Expected at tools/{tool_file_name}.",
                    location=f"tools/{tool_file_name}",
                )
            )
            continue

        # Try importing the module
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{os.path.basename(plugin_dir)}.tools.{tool_name}",
                tool_path,
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
        except Exception:
            issues.append(
                ValidationIssue(
                    type="warning",
                    message=f"Could not import tool module '{tool_file_name}': "
                            f"{traceback.format_exc(limit=0).strip()}",
                    location=f"tools/{tool_file_name}",
                )
            )

    return issues


def _run_all_validations(
    manifest_data: dict[str, Any],
    plugin_dir: str | None = None,
) -> list[ValidationIssue]:
    """Run all validation checks and return combined issues."""
    issues: list[ValidationIssue] = []

    # 1. Directory structure
    if plugin_dir:
        issues.extend(_validate_directory_structure(plugin_dir))

    # 2. Manifest schema
    issues.extend(_validate_manifest_schema(manifest_data))

    # 3. Tool schemas
    issues.extend(_validate_tool_schemas(manifest_data))

    # 4. Tool imports (only if we have a directory)
    if plugin_dir:
        tools = manifest_data.get("tools", [])
        issues.extend(_validate_tool_imports(plugin_dir, tools))

    return issues


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/plugin-validate", response_model=ValidationResult)
async def validate_plugin(
    payload: ValidateByPath | ValidateByManifest,
) -> ValidationResult:
    """Validate a plugin.

    Accepts either a plugin directory path or inline manifest content.

    Returns validation results including any warnings or errors.
    """
    plugin_dir: str | None = None
    manifest_data: dict[str, Any] | None = None
    plugin_name: str | None = None

    if isinstance(payload, ValidateByPath):
        # --- Validate by path ---
        resolved_dir = _find_plugin_root(payload.path)
        if not resolved_dir:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin directory not found: '{payload.path}'. "
                       f"Checked as absolute path and relative to plugins/ directory.",
            )

        plugin_dir = resolved_dir
        raw_manifest = _load_manifest_from_disk(plugin_dir)
        if raw_manifest is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not load plugin.yaml from '{plugin_dir}'. "
                       f"Ensure the file exists and is valid YAML.",
            )

        manifest_data = raw_manifest

    else:
        # --- Validate by inline manifest ---
        manifest_content = payload.manifest
        manifest_data = manifest_content.model_dump()

    # Extract name for the result
    plugin_name = manifest_data.get("name")

    # Run validations
    issues = _run_all_validations(manifest_data, plugin_dir=plugin_dir)

    errors = [i for i in issues if i.type == "error"]
    return ValidationResult(
        valid=len(errors) == 0,
        name=plugin_name,
        issues=issues,
        tool_count=len(manifest_data.get("tools", [])),
    )

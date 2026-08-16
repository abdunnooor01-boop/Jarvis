"""Developer API endpoints — system health, metrics, introspection, and diagnostics."""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import sys
import time
import traceback
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.plugin import Plugin
from app.models.task_plan import TaskPlan
from app.models.user import User
from app.plugin_system.plugin_manifest import PluginManifest, ToolManifest
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/dev", tags=["developer"])

# Track application start time
APP_START_TIME = time.time()


def _get_sanitized_config() -> dict[str, Any]:
    """Return sanitized configuration with secrets masked."""
    config: dict[str, Any] = {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "llm_model": settings.openai_model,
        "cors_origins": settings.cors_origins,
        "rate_limit_chat": settings.rate_limit_chat,
        "rate_limit_api": settings.rate_limit_api,
    }
    # Add database type (not the URL with credentials)
    db_url = settings.database_url
    if "postgresql" in db_url:
        config["database_type"] = "postgresql"
    elif "sqlite" in db_url:
        config["database_type"] = "sqlite"
    else:
        config["database_type"] = "unknown"

    # Indicate which API keys are configured (not the keys themselves)
    config["api_keys_configured"] = {
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "gemini": bool(settings.gemini_api_key),
        "tavily": bool(settings.tavily_api_key),
    }

    return config


async def _check_db_health(db: AsyncSession) -> dict[str, Any]:
    """Check database connectivity."""
    try:
        await db.execute(select(func.now()))
        return {"status": "healthy", "type": "postgresql" if "postgresql" in settings.database_url else "sqlite"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/health")
async def system_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """System health check — verify DB and core services."""
    db_health = await _check_db_health(db)

    return {
        "status": "healthy" if db_health["status"] == "healthy" else "degraded",
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - APP_START_TIME, 2),
        "services": {
            "database": db_health,
            "api": {"status": "healthy"},
        },
    }


@router.get("/metrics")
async def system_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Basic system metrics — user counts, activity, uptime."""
    # Count active users
    user_count_result = await db.execute(select(func.count(User.id)))
    total_users = user_count_result.scalar() or 0

    # Count conversations
    conv_count_result = await db.execute(select(func.count(Conversation.id)))
    total_conversations = conv_count_result.scalar() or 0

    # Count messages
    msg_count_result = await db.execute(select(func.count(Message.id)))
    total_messages = msg_count_result.scalar() or 0

    # Count task plans
    plan_count_result = await db.execute(select(func.count(TaskPlan.id)))
    total_task_plans = plan_count_result.scalar() or 0

    # Count audit log entries (tool calls, events)
    audit_count_result = await db.execute(select(func.count(AuditLog.id)))
    total_audit_entries = audit_count_result.scalar() or 0

    # Count plugins
    plugin_count_result = await db.execute(select(func.count(Plugin.id)))
    total_plugins = plugin_count_result.scalar() or 0

    return {
        "uptime_seconds": round(time.time() - APP_START_TIME, 2),
        "users": {
            "total": total_users,
        },
        "conversations": {
            "total": total_conversations,
        },
        "messages": {
            "total": total_messages,
        },
        "task_plans": {
            "total": total_task_plans,
        },
        "audit_log_entries": {
            "total": total_audit_entries,
        },
        "plugins": {
            "total": total_plugins,
        },
    }


@router.get("/system-info")
async def system_info(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """System information — version, runtime, and sanitized config."""
    return {
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
        },
        "runtime": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "hostname": platform.node(),
        },
        "configuration": _get_sanitized_config(),
    }


@router.get("/tools")
async def tool_introspection(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Full tool introspection — all registered tools, their schemas, and descriptions."""
    executor = ToolExecutor(skip_plugins=True)
    definitions = executor.get_tool_definitions()

    tools_list = []
    for defn in definitions:
        func_def = defn.get("function", {})
        tools_list.append(
            {
                "name": func_def.get("name"),
                "description": func_def.get("description"),
                "parameters": func_def.get("parameters", {}),
            }
        )

    return {
        "total_tools": len(tools_list),
        "tools": tools_list,
    }


@router.get("/plugins")
async def plugin_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Plugin status — all registered plugins with manifest details."""
    result = await db.execute(
        select(Plugin).order_by(Plugin.name)
    )
    plugins = result.scalars().all()

    plugin_list = []
    for plugin in plugins:
        manifest = plugin.manifest or {}
        plugin_list.append(
            {
                "id": str(plugin.id) if hasattr(plugin, "id") else plugin.name,
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
                "enabled": plugin.enabled,
                "type": plugin.type if hasattr(plugin, "type") else "unknown",
                "manifest": {
                    "entry_point": manifest.get("entry_point", ""),
                    "tools": manifest.get("tools", []),
                    "permissions": manifest.get("permissions", []),
                },
            }
        )

    return {
        "total_plugins": len(plugin_list),
        "plugins": plugin_list,
    }


# ---------------------------------------------------------------------------
# Plugin Validation
# ---------------------------------------------------------------------------


class ValidateByPath(BaseModel):
    """Validate a plugin by filesystem path."""

    path: str = Field(..., description="Absolute or relative path to the plugin directory.")


class ToolManifestContent(BaseModel):
    """A single tool definition, as it would appear in a manifest."""

    name: str = Field(..., description="Tool name in snake_case.")
    description: str = Field(..., description="What the tool does.")
    parameters: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for tool parameters.")


class ManifestContent(BaseModel):
    """Inline manifest content to validate."""

    name: str = Field(..., description="Plugin name.")
    version: str = Field(..., description="Semantic version string.")
    description: str = Field(..., description="Plugin description.")
    author: str | None = Field(None, description="Plugin author.")
    tools: list[ToolManifestContent] = Field(default_factory=list, description="List of tool definitions.")


class ValidateByManifest(BaseModel):
    """Validate a plugin by its manifest content."""

    manifest: ManifestContent = Field(..., description="The plugin manifest content to validate.")


class ValidationIssue(BaseModel):
    """A single validation issue (warning or error)."""

    type: str = Field(..., description="Either 'error' or 'warning'.")
    message: str = Field(..., description="Human-readable description of the issue.")
    location: str | None = Field(None, description="Where the issue was found.")


class ValidationResult(BaseModel):
    """Result of a plugin validation check."""

    valid: bool = Field(..., description="Whether the plugin passed validation (no errors).")
    name: str | None = Field(None, description="Plugin name extracted from the manifest.")
    issues: list[ValidationIssue] = Field(default_factory=list, description="Validation issues (warnings and errors).")
    tool_count: int = Field(0, description="Number of tools defined in the manifest.")


def _find_plugin_root(search_path: str) -> str | None:
    """Resolve a path to an actual plugin directory."""
    plugins_base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "plugins"))
    candidates = [search_path, os.path.join(plugins_base, search_path)]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return os.path.normpath(candidate)
    return None


def _validate_manifest_schema(manifest: dict[str, Any]) -> list[ValidationIssue]:
    """Validate a manifest dict against the expected schema."""
    issues: list[ValidationIssue] = []
    if not manifest.get("name"):
        issues.append(ValidationIssue(type="error", message="Manifest must have a 'name' field.", location="manifest"))
    if not manifest.get("version"):
        issues.append(ValidationIssue(type="error", message="Manifest must have a 'version' field.", location="manifest"))
    if not manifest.get("description"):
        issues.append(ValidationIssue(type="warning", message="Manifest should have a 'description' field.", location="manifest"))
    tools = manifest.get("tools", [])
    if not tools:
        issues.append(ValidationIssue(type="warning", message="Plugin defines no tools.", location="manifest"))
    return issues


def _validate_tool_imports(manifest: dict[str, Any], plugin_dir: str) -> list[ValidationIssue]:
    """Check that tool modules referenced in the manifest can be imported."""
    issues: list[ValidationIssue] = []
    tools = manifest.get("tools", [])
    for tool_def in tools:
        tool_name = tool_def.get("name", "unknown")
        tool_file = os.path.join(plugin_dir, "tools", f"{tool_name}.py")
        if not os.path.isfile(tool_file):
            issues.append(ValidationIssue(type="error", message=f"Tool file not found: {tool_file}", location=f"tool:{tool_name}"))
    return issues


@router.post("/plugin-validate", response_model=ValidationResult)
async def validate_plugin(body: ValidateByPath | ValidateByManifest) -> ValidationResult:
    """Validate a plugin — by path or by inline manifest content."""
    all_issues: list[ValidationIssue] = []
    manifest: dict[str, Any] | None = None
    plugin_name: str | None = None

    if isinstance(body, ValidateByPath):
        plugin_dir = _find_plugin_root(body.path)
        if not plugin_dir:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin directory not found: {body.path}")
        manifest_path = os.path.join(plugin_dir, "plugin.yaml")
        if not os.path.isfile(manifest_path):
            manifest_path = os.path.join(plugin_dir, "plugin.json")
        if not os.path.isfile(manifest_path):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No plugin.yaml or plugin.json found.")
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) if manifest_path.endswith(".yaml") else __import__("json").load(f)
        all_issues.extend(_validate_manifest_schema(manifest))
        all_issues.extend(_validate_tool_imports(manifest, plugin_dir))
    else:
        manifest = body.manifest.model_dump()
        all_issues.extend(_validate_manifest_schema(manifest))

    if manifest:
        plugin_name = manifest.get("name")
    tool_count = len(manifest.get("tools", [])) if manifest else 0
    errors = [i for i in all_issues if i.type == "error"]

    return ValidationResult(
        valid=len(errors) == 0,
        name=plugin_name,
        issues=all_issues,
        tool_count=tool_count,
    )
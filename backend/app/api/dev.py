"""Developer API endpoints — system health, metrics, introspection, and diagnostics."""

from __future__ import annotations

import platform
import sys
import time
from typing import Any

from fastapi import APIRouter, Depends
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
"""Audit logging — structured logging of security events.

Writes to both the audit_log database table and structured stdout logs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger("audit")

# Flag to track if audit database is available (lazy check)
_audit_db_available: bool | None = None


def _get_audit_session() -> Any | None:
    """Get a database session for audit logging, or None if unavailable."""
    try:
        from app.database import async_session_factory

        return async_session_factory()
    except Exception:
        return None


async def log_audit_event(
    event_type: str,
    actor_id: str | None = None,
    actor_ip: str | None = None,
    resource: str | None = None,
    action: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    """Log an audit event to both DB and stdout.

    Args:
        event_type: Category of event (login, tool_execution, plugin_load, etc.).
        actor_id: User ID who performed the action (if authenticated).
        actor_ip: IP address of the actor.
        resource: The resource being acted upon.
        action: The specific action performed.
        status: 'success' or 'failure'.
        details: Additional structured details.
    """
    timestamp = datetime.now(UTC).isoformat()

    # Always log to stdout
    log_data: dict[str, Any] = {
        "audit": True,
        "event_type": event_type,
        "actor_id": actor_id,
        "actor_ip": actor_ip,
        "resource": resource,
        "action": action,
        "status": status,
        "details": details or {},
        "timestamp": timestamp,
    }

    if status == "failure":
        logger.warning("Audit event", **log_data)
    else:
        logger.info("Audit event", **log_data)

    # Try to persist to database
    try:
        from app.database import async_session_factory
        from app.models.audit_log import AuditLog

        async with async_session_factory() as session:
            audit_entry = AuditLog(
                event_type=event_type,
                actor_id=actor_id,
                actor_ip=actor_ip,
                resource=resource,
                action=action,
                status=status,
                details=details or {},
            )
            session.add(audit_entry)
            await session.commit()
    except Exception:
        logger.warning("Failed to persist audit event to database", event_type=event_type)


# Convenience functions for common audit events


async def log_login_attempt(
    email: str,
    ip: str,
    success: bool,
    reason: str | None = None,
) -> None:
    """Log a login attempt."""
    await log_audit_event(
        event_type="login",
        actor_id=email,
        actor_ip=ip,
        resource="auth",
        action="login",
        status="success" if success else "failure",
        details={"reason": reason} if reason else None,
    )


async def log_tool_execution(
    user_id: str,
    tool_name: str,
    params: dict[str, Any],
    success: bool,
    result_summary: str | None = None,
) -> None:
    """Log a tool execution."""
    await log_audit_event(
        event_type="tool_execution",
        actor_id=user_id,
        resource=f"tool:{tool_name}",
        action="execute",
        status="success" if success else "failure",
        details={
            "params": params,
            "result_summary": result_summary,
        },
    )


async def log_plugin_load(
    plugin_name: str,
    success: bool,
    error: str | None = None,
) -> None:
    """Log a plugin load event."""
    await log_audit_event(
        event_type="plugin_load",
        resource=f"plugin:{plugin_name}",
        action="load",
        status="success" if success else "failure",
        details={"error": error} if error else None,
    )


async def log_permission_denied(
    user_id: str | None,
    resource: str,
    reason: str,
    ip: str | None = None,
) -> None:
    """Log a permission denied event."""
    await log_audit_event(
        event_type="permission_denied",
        actor_id=user_id,
        actor_ip=ip,
        resource=resource,
        action="access",
        status="failure",
        details={"reason": reason},
    )


async def log_token_blacklist(
    token_jti: str,
    user_id: str,
    reason: str = "logout",
) -> None:
    """Log a token blacklist event."""
    await log_audit_event(
        event_type="token_blacklist",
        actor_id=user_id,
        resource="auth",
        action="blacklist_token",
        status="success",
        details={"token_jti": token_jti, "reason": reason},
    )

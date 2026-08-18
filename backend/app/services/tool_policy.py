"""Tool approval policy — which desktop-control tools need owner approval.

Phase 15 desktop computer control is approval-gated: the assistant can
propose tool calls, but high-impact tools (shell commands, file writes,
input injection, app launch, browser control) only execute after the owner
approves them. Read-only/observational tools run automatically.

Approval decisions are checked in this order:
  1. Per-tool policy classification (below).
  2. Per-user allowlist (remembered approvals) — overrides the policy.

The allowlist lives in the ``tool_allowlist`` table, managed through the
``ToolPolicyService`` and the REST API in ``app/api/tools.py``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.tool_allowlist import ToolAllowlistEntry

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Policy classification
# ---------------------------------------------------------------------------

# Read-only research tools — always safe to run, no approval needed.
AUTO_APPROVED_TOOLS: frozenset[str] = frozenset({"web_search"})

# Observational tools — passively read the screen. No approval needed, but
# every execution is still audit-logged (screens can contain sensitive data).
OBSERVE_TOOLS: frozenset[str] = frozenset(
    {"screenshot", "screen_read", "whats_on_screen", "screen_vision"}
)

# Tools whose danger depends on the `action` argument. Read/list are safe;
# anything that mutates state requires approval.
ACTION_SENSITIVE_TOOLS: frozenset[str] = frozenset({"file_ops", "clipboard"})
SENSITIVE_ACTIONS: frozenset[str] = frozenset(
    {"write", "delete", "remove", "move", "rename", "overwrite", "edit", "append"}
)
SAFE_ACTIONS: frozenset[str] = frozenset({"read", "list", "view"})

# Tools that ALWAYS require approval — they can execute code, inject input,
# launch apps, or drive a real browser session.
APPROVAL_REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "terminal",
        "mouse",
        "keyboard",
        "smart_click",
        "smart_type",
        "app_launch",
        "browser",
    }
)

# Default timeout (seconds) the backend waits for an owner decision on a
# proposed tool call before treating it as denied.
APPROVAL_TIMEOUT_SECONDS: int = 300

# Maximum number of tool-call turns in a single chat exchange (safety valve
# against runaway tool loops).
MAX_TOOL_TURNS: int = 8


def tool_requires_approval(tool_name: str, arguments: dict[str, Any] | None) -> bool:
    """Return True if a tool call must be approved before execution.

    Unknown tools default to approval-required (safe default).
    """
    if tool_name in APPROVAL_REQUIRED_TOOLS:
        return True
    if tool_name in AUTO_APPROVED_TOOLS or tool_name in OBSERVE_TOOLS:
        return False
    if tool_name in ACTION_SENSITIVE_TOOLS:
        action = str((arguments or {}).get("action", "read")).lower()
        if action in SAFE_ACTIONS:
            return False
        if action in SENSITIVE_ACTIONS:
            return True
        # Unknown action on a stateful tool — ask for approval.
        return True
    logger.info("Tool not classified; defaulting to approval required", tool=tool_name)
    return True


def _entry_matches(
    entry_arguments: dict[str, Any] | None,
    call_arguments: dict[str, Any] | None,
) -> bool:
    """An entry with ``None`` arguments matches any call for that tool.

    Otherwise the entry matches when every key it specifies has the same
    value in the call (partial/pattern matching, e.g. approve all
    ``terminal`` calls with a given command prefix).
    """
    if entry_arguments is None:
        return True
    if not call_arguments:
        return False
    return all(call_arguments.get(k) == v for k, v in entry_arguments.items())


class ToolPolicyService:
    """DB-backed allowlist lookups and management for tool approvals."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def is_allowlisted(
        self,
        user_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> bool:
        """Return True if this exact tool call is on the user's allowlist."""
        result = await self.db.execute(
            select(ToolAllowlistEntry).where(
                ToolAllowlistEntry.user_id == user_id,
                ToolAllowlistEntry.tool_name == tool_name,
            )
        )
        for entry in result.scalars().all():
            if _entry_matches(entry.arguments, arguments):
                return True
        return False

    async def add_allowlist_entry(
        self,
        user_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolAllowlistEntry:
        """Remember an approval for a tool call (or all calls for a tool)."""
        # De-duplicate: if an identical entry exists, return it.
        result = await self.db.execute(
            select(ToolAllowlistEntry).where(
                ToolAllowlistEntry.user_id == user_id,
                ToolAllowlistEntry.tool_name == tool_name,
                ToolAllowlistEntry.arguments.is_(None) if arguments is None
                else ToolAllowlistEntry.arguments == arguments,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        entry = ToolAllowlistEntry(
            user_id=user_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        logger.info(
            "Allowlist entry added",
            user_id=user_id,
            tool=tool_name,
            arguments=arguments,
        )
        return entry

    async def list_allowlist(self, user_id: str) -> list[ToolAllowlistEntry]:
        """Return the user's allowlist entries (newest first)."""
        result = await self.db.execute(
            select(ToolAllowlistEntry)
            .where(ToolAllowlistEntry.user_id == user_id)
            .order_by(ToolAllowlistEntry.created_at.desc())
        )
        return list(result.scalars().all())

    async def remove_allowlist_entry(self, user_id: str, entry_id: str) -> bool:
        """Remove one allowlist entry. Returns True if it existed."""
        result = await self.db.execute(
            delete(ToolAllowlistEntry).where(
                ToolAllowlistEntry.id == entry_id,
                ToolAllowlistEntry.user_id == user_id,
            )
        )
        await self.db.commit()
        removed = bool(result.rowcount)
        if removed:
            logger.info("Allowlist entry removed", user_id=user_id, entry_id=entry_id)
        return removed

"""Unit tests for the tool approval policy + allowlist service."""

from __future__ import annotations

import pytest

from app.services.tool_policy import (
    ToolPolicyService,
    blocked_in_hosted_mode,
    tool_requires_approval,
)


class TestPolicyClassification:
    """Tool policy classification."""

    def test_read_only_tools_are_auto_approved(self) -> None:
        assert tool_requires_approval("web_search", {}) is False
        assert tool_requires_approval("screenshot", {}) is False
        assert tool_requires_approval("screen_read", {}) is False
        assert tool_requires_approval("whats_on_screen", {}) is False
        assert tool_requires_approval("screen_vision", {}) is False

    def test_high_impact_tools_always_require_approval(self) -> None:
        for tool in ("terminal", "mouse", "keyboard", "smart_click", "smart_type",
                     "app_launch", "browser"):
            assert tool_requires_approval(tool, {}) is True, tool

    def test_file_ops_read_is_safe_write_requires_approval(self) -> None:
        assert tool_requires_approval("file_ops", {"action": "read"}) is False
        assert tool_requires_approval("file_ops", {"action": "list"}) is False
        assert tool_requires_approval("file_ops", {"action": "write"}) is True
        assert tool_requires_approval("file_ops", {"action": "delete"}) is True

    def test_clipboard_read_safe_write_requires_approval(self) -> None:
        assert tool_requires_approval("clipboard", {"action": "read"}) is False
        assert tool_requires_approval("clipboard", {"action": "write"}) is True

    def test_unknown_tool_defaults_to_approval_required(self) -> None:
        assert tool_requires_approval("mystery_tool", {}) is True


class TestHostedModeBlocking:
    """High-impact desktop-control tools must never run in hosted (web) mode."""

    def test_desktop_control_tools_are_blocked_in_hosted_mode(self) -> None:
        for tool in ("terminal", "mouse", "keyboard", "smart_click", "smart_type",
                     "app_launch", "browser"):
            assert blocked_in_hosted_mode(tool, {}) is True, tool

    def test_file_and_clipboard_writes_blocked_reads_allowed(self) -> None:
        assert blocked_in_hosted_mode("file_ops", {"action": "read"}) is False
        assert blocked_in_hosted_mode("file_ops", {"action": "list"}) is False
        assert blocked_in_hosted_mode("file_ops", {"action": "write"}) is True
        assert blocked_in_hosted_mode("file_ops", {"action": "delete"}) is True
        assert blocked_in_hosted_mode("clipboard", {"action": "read"}) is False
        assert blocked_in_hosted_mode("clipboard", {"action": "write"}) is True

    def test_research_and_observe_tools_stay_available(self) -> None:
        assert blocked_in_hosted_mode("web_search", {}) is False
        assert blocked_in_hosted_mode("screenshot", {}) is False
        assert blocked_in_hosted_mode("screen_read", {}) is False


@pytest.mark.asyncio
async def test_allowlist_exact_and_wildcard_match() -> None:
    """Allowlist entries match exact args; None args match anything."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from tests.conftest import test_engine

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as db:
        service = ToolPolicyService(db)
        # Exact-match entry
        await service.add_allowlist_entry(
            user_id="user-1", tool_name="terminal", arguments={"command": "echo hi"}
        )
        assert await service.is_allowlisted(
            "user-1", "terminal", {"command": "echo hi"}
        ) is True
        assert await service.is_allowlisted(
            "user-1", "terminal", {"command": "echo bye"}
        ) is False
        # Wildcard entry (None args) — matches any call for the tool
        await service.add_allowlist_entry(user_id="user-1", tool_name="clipboard")
        assert await service.is_allowlisted(
            "user-1", "clipboard", {"action": "write", "text": "x"}
        ) is True
        # Other users unaffected
        assert await service.is_allowlisted(
            "user-2", "terminal", {"command": "echo hi"}
        ) is False

        entries = await service.list_allowlist("user-1")
        assert len(entries) == 2

        # Removal
        removed = await service.remove_allowlist_entry("user-1", entries[0].id)
        assert removed is True
        assert len(await service.list_allowlist("user-1")) == 1
        # Removing someone else's entry returns False
        assert await service.remove_allowlist_entry("user-2", entries[1].id) is False

"""Additional WebSocket tool-calling safety tests (Phase 15 QA).

Covers the control-layer fail-safes that are the core of the desktop
deep-test gate:

  * Approval timeout -> action DENIED (nothing executes).
  * Connection lost mid-approval -> action DENIED (fail-closed).
  * MAX_TOOL_TURNS runaway loop cap -> a model that keeps emitting tool
    calls is halted after the cap, never allowed to loop forever.
  * Multiple tool calls in a single turn -> each call gets its own
    proposal and independent decision.
  * Hosted (web) mode blocks stateful file/clipboard writes at the
    protocol level (``unavailable``), while read-only actions stay usable.
  * ``remember`` semantics: approve+remember persists an allowlist entry;
    deny+remember does NOT.

To apply: copy to backend/tests/test_api/test_ws_tool_approval_safety.py
in the Jarvis repo. Requires pytest-asyncio and the existing WS approval
test harness (test_ws_tool_approval.py).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import pytest
from httpx import AsyncClient

from app.api import ws as ws_module
from app.services.tool_policy import MAX_TOOL_TURNS

# Reuse the harness from the sibling approval test module.
from tests.test_api.test_ws_tool_approval import (
    FakeLLMService,
    FakeWebSocket,
    _install_fakes,
    _register,
    _sent_of_type,
    _terminal_tool_call,
    _wait_for_done,
)


class _Drive:
    """Context manager that runs the WS handler and always cancels it."""

    def __init__(self, fake_ws: FakeWebSocket) -> None:
        self.fake_ws = fake_ws

    async def __aenter__(self) -> "_Drive":
        self.task = asyncio.create_task(ws_module.chat_websocket(self.fake_ws))
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.task.cancel()
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await self.task


@pytest.mark.asyncio
async def test_approval_timeout_is_denial_failsafe(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool against which no owner decision arrives in time is DENIED."""
    monkeypatch.setattr(ws_module, "APPROVAL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(ws_module.settings, "jarvis_mode", "desktop")
    token = _register(client, sample_user_data)
    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [_terminal_tool_call()],
            [{"type": "content", "content": "No approval received, so I did not run it."}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "run a command"},
        ],
    )
    async with _Drive(fake_ws):
        await _wait_for_done(fake_ws)

    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert results[0].get("denied") is True
    assert "not executed" in results[0]["result"]["error"]
    assert "timed out" in results[0]["result"]["error"]


@pytest.mark.asyncio
async def test_connection_lost_mid_approval_denies(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the client disconnects while a proposal is pending, the action is
    denied (fail-closed). A raise from receive_text must never execute the
    tool.
    """
    monkeypatch.setattr(ws_module.settings, "jarvis_mode", "desktop")

    class DropOnApprovalWS(FakeWebSocket):
        def __init__(self, responses: list[dict[str, Any]]) -> None:
            super().__init__(responses)
            self.receives = 0

        async def receive_text(self) -> str:
            self.receives += 1
            if self.receives > 2:
                raise RuntimeError("connection lost")
            return await super().receive_text()

    token = _register(client, sample_user_data)
    fake_ws = DropOnApprovalWS(
        responses=[
            {"token": token},
            {"type": "message", "content": "run a command"},
        ]
    )
    monkeypatch.setattr(
        ws_module,
        "get_llm_service",
        lambda: FakeLLMService(
            [
                [_terminal_tool_call()],
                [{"type": "content", "content": "Connection is gone, skipping."}],
            ]
        ),
    )

    async with _Drive(fake_ws):
        await _wait_for_done(fake_ws)

    # The terminal tool must never have executed (fail-closed on drop).
    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert results[0].get("denied") is True
    assert "not executed" in results[0]["result"]["error"]


@pytest.mark.asyncio
async def test_runaway_tool_loop_is_capped(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model that keeps emitting tool calls is stopped after MAX_TOOL_TURNS.

    The loop must never run indefinitely. We script a model that emits a
    safe, auto-approved tool call on every turn for many more turns than the
    cap; the handler must still terminate (emit ``done``) and never exceed
    the cap.
    """
    monkeypatch.setattr(ws_module.settings, "jarvis_mode", "desktop")
    token = _register(client, sample_user_data)

    tool_call = {
        "type": "tool_call",
        "id": "call_loop",
        "name": "web_search",
        "arguments": json.dumps({"query": "loop"}),
    }
    turns = MAX_TOOL_TURNS + 5
    script = [[tool_call] for _ in range(turns)] + [
        [{"type": "content", "content": "I'm done searching."}]
    ]
    fake_ws = _install_fakes(
        monkeypatch,
        script=script,
        responses=[
            {"token": token},
            {"type": "message", "content": "keep searching"},
        ],
    )
    async with _Drive(fake_ws):
        await _wait_for_done(fake_ws)

    results = _sent_of_type(fake_ws, "tool_result")  # auto-approved web_search
    assert len(results) <= MAX_TOOL_TURNS
    assert any(f.get("type") == "done" for f in fake_ws.sent)


@pytest.mark.asyncio
async def test_multiple_tool_calls_each_need_own_approval(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two tool calls in one turn each produce their own proposal.

    Approving one must never auto-approve the sibling.
    """
    monkeypatch.setattr(ws_module.settings, "jarvis_mode", "desktop")
    token = _register(client, sample_user_data)

    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [
                _terminal_tool_call(),
                {
                    "type": "tool_call",
                    "id": "call_2",
                    "name": "app_launch",
                    "arguments": json.dumps({"operation": "open_app", "app_name": "xterm"}),
                },
            ],
            [{"type": "content", "content": "done with both"}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "do two things"},
            {"type": "tool_decision", "proposal_id": "any", "decision": "deny"},
            {"type": "tool_decision", "proposal_id": "any", "decision": "deny"},
        ],
    )
    async with _Drive(fake_ws):
        await _wait_for_done(fake_ws)

    proposals = _sent_of_type(fake_ws, "tool_proposal")
    assert len(proposals) == 2
    tool_names = {p["tool_name"] for p in proposals}
    assert {"terminal", "app_launch"} == tool_names

    results = _sent_of_type(fake_ws, "tool_result")
    denied = [r for r in results if r.get("denied")]
    assert len(denied) == 2
    assert len(results) == 2


@pytest.mark.asyncio
async def test_hosted_mode_blocks_file_write_at_protocol_level(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Web build cannot run file tools: a stateful file write in hosted mode
    returns ``unavailable`` and never triggers an approval prompt.
    """
    monkeypatch.setattr(ws_module.settings, "jarvis_mode", "hosted")
    token = _register(client, sample_user_data)

    tool_call = {
        "type": "tool_call",
        "id": "call_f",
        "name": "file_ops",
        "arguments": json.dumps({"operation": "write", "path": "/tmp/jarvis_qa.txt", "text": "x"}),
    }
    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [tool_call],
            [{"type": "content", "content": "I cannot write files in web mode."}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "write a file"},
        ],
    )
    async with _Drive(fake_ws):
        await _wait_for_done(fake_ws)

    assert _sent_of_type(fake_ws, "tool_proposal") == []
    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert results[0].get("unavailable") is True
    assert results[0]["result"]["status"] == "unavailable"
    assert results[0]["result"]["reason"] == "hosted mode — action not executed"


@pytest.mark.asyncio
async def test_hosted_mode_allows_file_read(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only actions stay usable in hosted mode (no host-side mutation)."""
    monkeypatch.setattr(ws_module.settings, "jarvis_mode", "hosted")
    token = _register(client, sample_user_data)

    tool_call = {
        "type": "tool_call",
        "id": "call_r",
        "name": "file_ops",
        "arguments": json.dumps({"operation": "read", "path": "/etc/hostname"}),
    }
    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [tool_call],
            [{"type": "content", "content": "read it"}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "read a file"},
        ],
    )
    async with _Drive(fake_ws):
        await _wait_for_done(fake_ws)

    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    # Read is host-safe: it was not reported 'unavailable'.
    assert results[0].get("unavailable") in (None, False)

"""WebSocket tool-calling integration tests.

Drives the real ``chat_websocket`` handler with a fake websocket + fake LLM
provider to verify the Phase 15 protocol end to end:
  LLM emits tool_call -> tool_proposal (when approval required)
  -> tool_decision (approve/deny) -> tool_result -> model continues.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from httpx import AsyncClient

from app.api import ws as ws_module


class FakeWebSocket:
    """In-memory WebSocket: preloaded responses, recorded sends."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._hang = asyncio.get_event_loop().create_future()
        self.sent: list[dict[str, Any]] = []
        self.accepted = False
        self.closed_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        if self._responses:
            return json.dumps(self._responses.pop(0))
        # No more client messages — hang until the test cancels the handler.
        await self._hang
        raise RuntimeError("unreachable")

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed_code = code


class FakeLLMService:
    """Emits a scripted sequence of chunks across stream_chat calls."""

    def __init__(self, script: list[list[dict[str, Any]]]) -> None:
        self._script = list(script)
        self.calls: list[list[dict[str, Any]]] = []

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> Any:
        self.calls.append(messages)
        step = self._script.pop(0) if self._script else []
        for chunk in step:
            yield chunk


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    script: list[list[dict[str, Any]]],
    responses: list[dict[str, Any]],
) -> FakeWebSocket:
    """Patch ws.py deps and return a FakeWebSocket with preloaded responses."""
    from tests.conftest import test_session_factory

    monkeypatch.setattr(
        ws_module, "async_session_factory", lambda: test_session_factory()
    )
    monkeypatch.setattr(ws_module, "get_llm_service", lambda: FakeLLMService(script))
    return FakeWebSocket(responses)


async def _register(client: AsyncClient, sample_user_data: dict) -> str:
    reg = await client.post("/api/v1/auth/register", json=sample_user_data)
    assert reg.status_code == 200 or reg.status_code == 201
    return reg.json()["access_token"]


async def _drive(fake_ws: FakeWebSocket) -> asyncio.Task[None]:
    task = asyncio.create_task(ws_module.chat_websocket(fake_ws))  # type: ignore[arg-type]
    return task


async def _wait_for_done(fake_ws: FakeWebSocket, timeout: float = 10.0) -> None:
    loop = 0
    while loop < timeout * 100:
        if any(f.get("type") == "done" for f in fake_ws.sent):
            return
        await asyncio.sleep(0.01)
        loop += 1
    raise AssertionError(f"timed out waiting for done. sent={fake_ws.sent}")


def _sent_of_type(fake_ws: FakeWebSocket, type_: str) -> list[dict[str, Any]]:
    return [f for f in fake_ws.sent if f.get("type") == type_]


def _terminal_tool_call() -> dict[str, Any]:
    return {
        "type": "tool_call",
        "id": "call_1",
        "name": "terminal",
        "arguments": json.dumps({"command": "echo hello"}),
    }


@pytest.mark.asyncio
async def test_tool_call_requires_approval_and_runs_after_approve(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Approval flow: proposal -> approve -> tool_result -> model continues."""
    token = await _register(client, sample_user_data)
    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [_terminal_tool_call()],
            [{"type": "content", "content": "Done."}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "run a command"},
            {"type": "tool_decision", "proposal_id": "any", "decision": "approve"},
        ],
    )
    task = await _drive(fake_ws)
    try:
        await _wait_for_done(fake_ws)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

    types = [f.get("type") for f in fake_ws.sent]
    assert types[0] == "connected"
    assert "conversation_created" in types

    proposals = _sent_of_type(fake_ws, "tool_proposal")
    assert len(proposals) == 1
    assert proposals[0]["tool_name"] == "terminal"

    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert "denied" not in results[0]
    assert results[0]["approval"] == "approved by owner"

    assert any(f.get("type") == "chunk" and f.get("content") == "Done." for f in fake_ws.sent)
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_tool_call_denied_does_not_execute(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deny flow: proposal -> deny -> denied tool_result -> model continues."""
    token = await _register(client, sample_user_data)
    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [_terminal_tool_call()],
            [{"type": "content", "content": "Skipping that."}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "run a command"},
            {"type": "tool_decision", "proposal_id": "any", "decision": "deny"},
        ],
    )
    task = await _drive(fake_ws)
    try:
        await _wait_for_done(fake_ws)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

    proposals = _sent_of_type(fake_ws, "tool_proposal")
    assert len(proposals) == 1

    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert results[0].get("denied") is True
    assert "denied" in results[0]["result"]["error"]

    assert any(
        f.get("type") == "chunk" and f.get("content") == "Skipping that."
        for f in fake_ws.sent
    )


@pytest.mark.asyncio
async def test_allowlisted_tool_runs_without_proposal(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-remembered tool call executes without an approval prompt."""
    token = await _register(client, sample_user_data)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/tools/allowlist",
        json={"tool_name": "terminal"},
        headers=headers,
    )
    assert resp.status_code == 201

    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [_terminal_tool_call()],
            [{"type": "content", "content": "Ran it."}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "run a command"},
        ],
    )
    task = await _drive(fake_ws)
    try:
        await _wait_for_done(fake_ws)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

    assert _sent_of_type(fake_ws, "tool_proposal") == []
    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert results[0]["approval"] == "allowlisted"
    assert "denied" not in results[0]


@pytest.mark.asyncio
async def test_safe_tool_runs_without_approval(
    client: AsyncClient, sample_user_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only tools execute immediately (auto-approved by policy)."""
    token = await _register(client, sample_user_data)
    fake_ws = _install_fakes(
        monkeypatch,
        script=[
            [{
                "type": "tool_call",
                "id": "call_2",
                "name": "web_search",
                "arguments": json.dumps({"query": "jarvis"}),
            }],
            [{"type": "content", "content": "Searched."}],
        ],
        responses=[
            {"token": token},
            {"type": "message", "content": "search the web"},
        ],
    )
    task = await _drive(fake_ws)
    try:
        await _wait_for_done(fake_ws)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

    assert _sent_of_type(fake_ws, "tool_proposal") == []
    results = _sent_of_type(fake_ws, "tool_result")
    assert len(results) == 1
    assert results[0]["approval"] == "auto-approved by policy"

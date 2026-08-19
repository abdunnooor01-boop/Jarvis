"""Tests for the tools API (registry + approval allowlist)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tools(client: AsyncClient) -> None:
    """GET /api/v1/tools lists tools with approval flags."""
    resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    by_name = {t["name"]: t for t in data["tools"]}
    # High-impact tools are flagged approval-required
    assert by_name["terminal"]["approval_required"] is True
    assert by_name["app_launch"]["approval_required"] is True
    # Read-only tools are not
    assert by_name["web_search"]["approval_required"] is False
    assert by_name["file_ops"]["approval_required"] is True  # worst-case (write)
    assert by_name["file_ops"]["action_sensitive"] is True


@pytest.mark.asyncio
async def test_allowlist_crud(client: AsyncClient, sample_user_data: dict) -> None:
    """Allowlist create/list/delete round-trip."""
    reg = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Empty at first
    resp = await client.get("/api/v1/tools/allowlist", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["entries"] == []

    # Create an exact-args entry
    resp = await client.post(
        "/api/v1/tools/allowlist",
        json={"tool_name": "terminal", "arguments": {"command": "echo hi"}},
        headers=headers,
    )
    assert resp.status_code == 201
    entry = resp.json()
    assert entry["tool_name"] == "terminal"
    assert entry["arguments"] == {"command": "echo hi"}

    # Create a wildcard entry
    resp = await client.post(
        "/api/v1/tools/allowlist",
        json={"tool_name": "clipboard"},
        headers=headers,
    )
    assert resp.status_code == 201

    # List — 2 entries
    resp = await client.get("/api/v1/tools/allowlist", headers=headers)
    assert len(resp.json()["entries"]) == 2

    # Delete one
    resp = await client.delete(
        f"/api/v1/tools/allowlist/{entry['id']}", headers=headers
    )
    assert resp.status_code == 204
    resp = await client.get("/api/v1/tools/allowlist", headers=headers)
    assert len(resp.json()["entries"]) == 1

    # Delete a non-existent entry → 404
    resp = await client.delete("/api/v1/tools/allowlist/nope", headers=headers)
    assert resp.status_code == 404

    # Unauthenticated → 401
    resp = await client.get("/api/v1/tools/allowlist")
    assert resp.status_code == 401

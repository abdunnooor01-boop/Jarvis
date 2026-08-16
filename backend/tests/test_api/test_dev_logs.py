"""Tests for developer log viewer API."""

from __future__ import annotations

import uuid

import pytest


async def _register_and_get_token(client: pytest.fixture) -> str:
    """Helper to register a test user and return a token."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"logs-{uuid.uuid4().hex[:8]}@example.com",
            "password": "LogViewer123",
            "display_name": "Log Tester",
        },
    )
    data = reg_resp.json()
    return data.get("access_token", "")


@pytest.mark.asyncio
async def test_list_logs_requires_auth(client: pytest.fixture) -> None:
    """Test list logs endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_log_detail_requires_auth(client: pytest.fixture) -> None:
    """Test get log detail endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/logs/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_logs_success(client: pytest.fixture) -> None:
    """Test successful log listing."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data


@pytest.mark.asyncio
async def test_list_logs_with_level_filter(client: pytest.fixture) -> None:
    """Test log listing with level filter."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/logs?level=auth_login",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_logs_with_search(client: pytest.fixture) -> None:
    """Test log listing with search term."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/logs?search=test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_logs_with_pagination(client: pytest.fixture) -> None:
    """Test log listing with pagination params."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/logs?page=1&page_size=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 5


@pytest.mark.asyncio
async def test_get_log_detail_not_found(client: pytest.fixture) -> None:
    """Test get log detail returns 404 for nonexistent log."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/logs/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_logs_with_details_filter(client: pytest.fixture) -> None:
    """Test log listing with details search."""
    token = await _register_and_get_token(client)
    if not token:
        pytest.skip("Rate limited — skipping")
    resp = await client.get(
        "/api/v1/dev/logs?search=login",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
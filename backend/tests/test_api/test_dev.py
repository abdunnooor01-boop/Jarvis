"""Tests for developer API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_health_requires_auth(client: pytest.fixture) -> None:
    """Test health endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metrics_requires_auth(client: pytest.fixture) -> None:
    """Test metrics endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/metrics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_system_info_requires_auth(client: pytest.fixture) -> None:
    """Test system-info endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/system-info")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tools_requires_auth(client: pytest.fixture) -> None:
    """Test tools endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/tools")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_plugins_requires_auth(client: pytest.fixture) -> None:
    """Test plugins endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/dev/plugins")
    assert resp.status_code == 401


async def _register_and_get_token(client: pytest.fixture) -> str:
    """Helper to register a test user and return a token."""
    import uuid

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"dev-{uuid.uuid4().hex[:8]}@example.com",
            "password": "DevTestPass123",
            "display_name": "Dev Tester",
        },
    )
    data = reg_resp.json()
    return data.get("access_token", "")


@pytest.mark.asyncio
async def test_health_success(client: pytest.fixture) -> None:
    """Test successful health check."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]


@pytest.mark.asyncio
async def test_metrics_success(client: pytest.fixture) -> None:
    """Test successful metrics retrieval."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "uptime_seconds" in data
    assert "users" in data
    assert "messages" in data


@pytest.mark.asyncio
async def test_system_info_success(client: pytest.fixture) -> None:
    """Test successful system info retrieval."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/system-info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "application" in data
    assert "runtime" in data
    assert "configuration" in data
    # Sanitized config should not contain raw API keys
    config = data["configuration"]
    assert "openai" not in str(data) or "api_keys_configured" in config


@pytest.mark.asyncio
async def test_tools_success(client: pytest.fixture) -> None:
    """Test successful tool introspection."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/tools",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_tools" in data
    assert "tools" in data
    assert isinstance(data["tools"], list)
    if data["tools"]:
        assert "name" in data["tools"][0]
        assert "description" in data["tools"][0]


@pytest.mark.asyncio
async def test_plugins_success(client: pytest.fixture) -> None:
    """Test successful plugin status retrieval."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/dev/plugins",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_plugins" in data
    assert "plugins" in data
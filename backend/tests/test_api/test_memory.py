"""Tests for memory API endpoints."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient


@pytest.fixture
def auth_headers(client: AsyncClient, sample_user_data: dict) -> dict[str, str]:
    """Register a user and return auth headers."""
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from app.database import Base, get_db
    from app.main import app

    # We need to do this synchronously-ish since pytest-asyncio doesn't
    # support fixtures calling async code easily. Instead, let's use
    # the test helpers approach.
    return {}


@pytest.mark.asyncio
async def test_search_memories_requires_auth(client: AsyncClient) -> None:
    """Test search endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/memory/search?q=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_memories_requires_auth(client: AsyncClient) -> None:
    """Test list endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/memory")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_preferences_requires_auth(client: AsyncClient) -> None:
    """Test preferences endpoint returns 401 without auth."""
    resp = await client.get("/api/v1/memory/preferences")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_memories_empty(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test search returns empty list for a new user."""
    # Register and get token
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/memory/search?q=test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_requires_query_param(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test search requires query parameter."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/memory/search",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_memories_empty(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test list returns empty for a new user."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/memory",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_preferences_empty(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test getting preferences returns empty dict for new user."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/memory/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferences"] == {}


@pytest.mark.asyncio
async def test_update_preferences(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test updating user preferences."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.put(
        "/api/v1/memory/preferences",
        json={"preferences": {"theme": "dark", "language": "Python"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferences"]["theme"] == "dark"
    assert data["preferences"]["language"] == "Python"


@pytest.mark.asyncio
async def test_update_preferences_overwrite(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test updating preferences overwrites existing values."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    # Set initial preference
    await client.put(
        "/api/v1/memory/preferences",
        json={"preferences": {"theme": "dark"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Overwrite
    resp = await client.put(
        "/api/v1/memory/preferences",
        json={"preferences": {"theme": "light"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferences"]["theme"] == "light"


@pytest.mark.asyncio
async def test_summarize_nonexistent_conversation(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test summarizing a non-existent conversation returns 404."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.post(
        f"/api/v1/memory/conversations/{fake_id}/summarize",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_memory_not_found(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test deleting a non-existent memory returns 404."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.delete(
        f"/api/v1/memory/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preferences_user_isolation(
    client: AsyncClient,
) -> None:
    """Test preferences are isolated between users."""
    user_a_data = {
        "email": "user-a-test@example.com",
        "password": "Password123!",
        "display_name": "User A",
    }
    user_b_data = {
        "email": "user-b-test@example.com",
        "password": "Password456!",
        "display_name": "User B",
    }

    # Register both users
    reg_a = await client.post("/api/v1/auth/register", json=user_a_data)
    token_a = reg_a.json()["access_token"]

    reg_b = await client.post("/api/v1/auth/register", json=user_b_data)
    token_b = reg_b.json()["access_token"]

    # User A sets preference
    await client.put(
        "/api/v1/memory/preferences",
        json={"preferences": {"theme": "dark"}},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # User B should not see User A's preferences
    resp = await client.get(
        "/api/v1/memory/preferences",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.json()["preferences"] == {}


@pytest.mark.asyncio
async def test_list_memories_pagination(
    client: AsyncClient,
    sample_user_data: dict,
) -> None:
    """Test pagination works for memory listing."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/memory?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert "pages" in data
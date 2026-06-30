"""Tests for chat API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient, sample_user_data: dict) -> None:
    """Test creating a new conversation."""
    # Register and get token
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    # Create conversation
    resp = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Test Conversation"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Conversation"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_conversations(client: AsyncClient, sample_user_data: dict) -> None:
    """Test listing user conversations."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    # Create two conversations
    await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Conv 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Conv 2"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # List conversations
    resp = await client.get(
        "/api/v1/chat/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_conversation_not_found(client: AsyncClient, sample_user_data: dict) -> None:
    """Test getting a non-existent conversation returns 404."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient, sample_user_data: dict) -> None:
    """Test soft-deleting a conversation."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    # Create conversation
    create_resp = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "To Delete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    conv_id = create_resp.json()["id"]

    # Delete it
    resp = await client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Verify it's gone
    list_resp = await client.get(
        "/api/v1/chat/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test the health check endpoint."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
"""Tests for auth API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient, sample_user_data: dict) -> None:
    """Test user registration and subsequent login."""
    # Register
    resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Login with same credentials
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, sample_user_data: dict) -> None:
    """Test that registering with an existing email returns 409."""
    await client.post("/api/v1/auth/register", json=sample_user_data)
    resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    """Test login with wrong credentials returns 401."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, sample_user_data: dict) -> None:
    """Test that /me returns the user profile with a valid token."""
    # Register
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    # Get profile
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == sample_user_data["email"]
    assert data["display_name"] == sample_user_data["display_name"]


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    """Test that /me returns 401 without a token."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, sample_user_data: dict) -> None:
    """Test refreshing an access token."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    refresh_token = reg_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

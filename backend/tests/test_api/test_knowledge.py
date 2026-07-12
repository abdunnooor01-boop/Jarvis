"""Tests for knowledge feed API — sources, entries, and seeding."""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_list_sources_public(client):
    """Test listing knowledge sources without auth."""
    resp = await client.get("/api/v1/knowledge/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] > 0
    # Check first source has expected fields
    first = data["items"][0]
    assert "id" in first
    assert "name" in first
    assert "source_type" in first
    assert "url" in first
    assert "schedule" in first


@pytest.mark.asyncio
async def test_list_sources_has_default_seeds(client):
    """Test that all default sources are seeded."""
    resp = await client.get("/api/v1/knowledge/sources")
    data = resp.json()
    assert data["total"] >= 14  # 14 default sources
    names = {s["name"] for s in data["items"]}
    assert "Hacker News Top Stories" in names
    assert "GitHub Trending — AI/ML" in names
    assert "Python.org Blog (RSS)" in names
    assert "OpenAI Blog (RSS)" in names
    assert "ArXiv AI Papers (RSS)" in names


@pytest.mark.asyncio
async def test_list_sources_types(client):
    """Test that sources have correct types."""
    resp = await client.get("/api/v1/knowledge/sources")
    data = resp.json()
    types = {s["source_type"] for s in data["items"]}
    assert "rss" in types
    assert "api" in types
    # All types should be valid
    for s in data["items"]:
        assert s["source_type"] in ("rss", "api", "page")


@pytest.mark.asyncio
async def test_get_source_success(client):
    """Test getting a specific source by ID."""
    resp = await client.get("/api/v1/knowledge/sources")
    source_id = resp.json()["items"][0]["id"]

    detail_resp = await client.get(f"/api/v1/knowledge/sources/{source_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == source_id
    assert "name" in detail
    assert "url" in detail


@pytest.mark.asyncio
async def test_get_source_not_found(client):
    """Test getting a non-existent source."""
    resp = await client.get(f"/api/v1/knowledge/sources/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_source_requires_auth(client):
    """Test creating a source returns 401 without auth."""
    resp = await client.post(
        "/api/v1/knowledge/sources",
        json={
            "name": "Test Source",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_source_success(client):
    """Test creating a new source with auth."""
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/api/v1/knowledge/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "My Custom Blog",
            "source_type": "rss",
            "url": "https://example.com/feed.xml",
            "schedule": "daily",
            "category": "python",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Custom Blog"
    assert data["source_type"] == "rss"
    assert data["url"] == "https://example.com/feed.xml"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_create_source_invalid_type(client):
    """Test creating a source with invalid type."""
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/api/v1/knowledge/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Bad Source",
            "source_type": "invalid_type",
            "url": "https://example.com",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_entries_requires_auth(client):
    """Test listing entries returns 401 without auth."""
    resp = await client.get("/api/v1/knowledge/entries")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_entries_empty(client):
    """Test listing entries with auth returns empty list initially."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/knowledge/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_entry_not_found(client):
    """Test getting a non-existent entry."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        f"/api/v1/knowledge/entries/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_entry_reviewed_requires_auth(client):
    """Test marking entry reviewed returns 401 without auth."""
    resp = await client.post(
        f"/api/v1/knowledge/entries/{uuid.uuid4()}/review"
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mark_entry_reviewed_not_found(client):
    """Test marking a non-existent entry."""
    token = await _register_and_get_token(client)
    resp = await client.post(
        f"/api/v1/knowledge/entries/{uuid.uuid4()}/review",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def _register_and_get_token(client) -> str:
    """Helper to register a test user and return a token."""
    import uuid as _uuid

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"knowledge-{_uuid.uuid4().hex[:8]}@example.com",
            "password": "KnowTest123",
            "display_name": "Knowledge Tester",
        },
    )
    data = reg_resp.json()
    return data.get("access_token", "")
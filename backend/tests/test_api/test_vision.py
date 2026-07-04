"""Tests for vision API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_analyze_requires_auth(client: pytest.fixture) -> None:
    """Test analyze endpoint returns 401 without auth."""
    resp = await client.post(
        "/api/v1/vision/analyze",
        json={"image": "dGVzdA==", "prompt": "test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_find_requires_auth(client: pytest.fixture) -> None:
    """Test find endpoint returns 401 without auth."""
    resp = await client.post(
        "/api/v1/vision/find",
        json={"image": "dGVzdA==", "description": "button"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_describe_requires_auth(client: pytest.fixture) -> None:
    """Test describe endpoint returns 401 without auth."""
    resp = await client.post(
        "/api/v1/vision/describe",
        json={"image": "dGVzdA=="},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_requires_auth(client: pytest.fixture) -> None:
    """Test compare endpoint returns 401 without auth."""
    resp = await client.post(
        "/api/v1/vision/compare",
        json={"image_a": "dGVzdA==", "image_b": "dGVzdA=="},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_extract_text_requires_auth(client: pytest.fixture) -> None:
    """Test extract-text endpoint returns 401 without auth."""
    resp = await client.post(
        "/api/v1/vision/extract-text",
        json={"image": "dGVzdA=="},
    )
    assert resp.status_code == 401


async def _register_and_get_token(client: pytest.fixture) -> str:
    """Helper to register a test user with a valid password and return a token."""
    import uuid

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"vision-{uuid.uuid4().hex[:8]}@example.com",
            "password": "VisionTest123",
            "display_name": "Vision Tester",
        },
    )
    data = reg_resp.json()
    # If registration fails (e.g. existing bcrypt issue), try to login instead
    if "access_token" not in data:
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": data.get("email", "test@example.com"),
                "password": "VisionTest123",
            },
        )
        return login_resp.json().get("access_token", "")
    return data["access_token"]


@pytest.mark.asyncio
async def test_analyze_invalid_base64(client: pytest.fixture) -> None:
    """Test analyze with invalid base64 returns 400."""
    token = await _register_and_get_token(client)

    resp = await client.post(
        "/api/v1/vision/analyze",
        json={"image": "!!!invalid-base64!!!", "prompt": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_analyze_success(client: pytest.fixture) -> None:
    """Test successful analyze request."""
    token = await _register_and_get_token(client)

    import base64

    img_b64 = base64.b64encode(b"fake-image-data").decode()

    with patch("app.services.vision.VisionService.analyze_screenshot") as mock_analyze:
        mock_analyze.return_value = {
            "description": "A screenshot with UI elements",
            "model": "gpt-4o",
            "processing_time_ms": 150.0,
        }

        resp = await client.post(
            "/api/v1/vision/analyze",
            json={"image": img_b64, "prompt": "What do you see?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "A screenshot with UI elements"
    assert data["model"] == "gpt-4o"
    assert data["processing_time_ms"] == 150.0


@pytest.mark.asyncio
async def test_find_element_success(client: pytest.fixture) -> None:
    """Test successful find element request."""
    token = await _register_and_get_token(client)

    import base64

    img_b64 = base64.b64encode(b"fake-image-data").decode()

    with patch("app.services.vision.VisionService.find_element") as mock_find:
        mock_find.return_value = {
            "found": True,
            "x": 100,
            "y": 200,
            "width": 50,
            "height": 30,
            "confidence": 0.95,
            "label": "Login Button",
            "explanation": "Found in center",
        }

        resp = await client.post(
            "/api/v1/vision/find",
            json={"image": img_b64, "description": "the login button"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["x"] == 100
    assert data["y"] == 200
    assert data["confidence"] == 0.95


@pytest.mark.asyncio
async def test_find_element_empty_description(client: pytest.fixture) -> None:
    """Test find element with empty description returns 400."""
    token = await _register_and_get_token(client)

    resp = await client.post(
        "/api/v1/vision/find",
        json={"image": "dGVzdA==", "description": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_describe_success(client: pytest.fixture) -> None:
    """Test successful describe request."""
    token = await _register_and_get_token(client)

    import base64

    img_b64 = base64.b64encode(b"fake-image-data").decode()

    with patch("app.services.vision.VisionService.describe_screen") as mock_describe:
        mock_describe.return_value = {
            "description": "A screen with a dark theme and a login form",
            "model": "gpt-4o",
            "processing_time_ms": 200.0,
        }

        resp = await client.post(
            "/api/v1/vision/describe",
            json={"image": img_b64},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "description" in data
    assert "processing_time_ms" in data


@pytest.mark.asyncio
async def test_compare_success(client: pytest.fixture) -> None:
    """Test successful compare request."""
    token = await _register_and_get_token(client)

    import base64

    img_b64 = base64.b64encode(b"fake-image-data").decode()

    with patch("app.services.vision.VisionService.compare_screenshots") as mock_compare:
        mock_compare.return_value = {
            "changes_detected": True,
            "description": "The button color changed from blue to green",
            "model": "gpt-4o",
            "processing_time_ms": 300.0,
        }

        resp = await client.post(
            "/api/v1/vision/compare",
            json={"image_a": img_b64, "image_b": img_b64},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["changes_detected"] is True
    assert "description" in data


@pytest.mark.asyncio
async def test_extract_text_success(client: pytest.fixture) -> None:
    """Test successful extract-text request."""
    token = await _register_and_get_token(client)

    import base64

    img_b64 = base64.b64encode(b"fake-image-data").decode()

    with patch("app.services.vision.VisionService.extract_text_regions") as mock_extract:
        mock_extract.return_value = {
            "regions": [
                {
                    "text": "Hello",
                    "x": 10,
                    "y": 20,
                    "width": 50,
                    "height": 20,
                    "confidence": 0.9,
                }
            ],
            "full_text": "Hello",
            "model": "gpt-4o",
            "processing_time_ms": 180.0,
        }

        resp = await client.post(
            "/api/v1/vision/extract-text",
            json={"image": img_b64},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["regions"]) == 1
    assert data["full_text"] == "Hello"
    assert data["regions"][0]["text"] == "Hello"
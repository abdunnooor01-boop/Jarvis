"""Tests for voice API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_transcribe_success(client: AsyncClient, sample_user_data: dict) -> None:
    """Test successful audio transcription."""
    # Register and get token
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    mock_voice = AsyncMock()
    mock_voice.transcribe = AsyncMock(return_value="Hello, this is a test.")

    with patch("app.api.voice.get_voice_service", return_value=mock_voice):
        resp = await client.post(
            "/api/v1/voice/transcribe",
            files={"file": ("test.wav", b"fake_wav_data", "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Hello, this is a test."


@pytest.mark.asyncio
async def test_transcribe_no_file(client: AsyncClient, sample_user_data: dict) -> None:
    """Test transcription with no file returns 400."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # FastAPI validation returns 422


@pytest.mark.asyncio
async def test_transcribe_unauthorized(client: AsyncClient) -> None:
    """Test transcription without auth returns 401."""
    resp = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("test.wav", b"data", "audio/wav")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_synthesize_success(client: AsyncClient, sample_user_data: dict) -> None:
    """Test successful TTS synthesis."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    mock_voice = AsyncMock()

    async def mock_synthesize(text: str):
        yield b"mp3_chunk_1"
        yield b"mp3_chunk_2"

    mock_voice.synthesize = mock_synthesize

    with patch("app.api.voice.get_voice_service", return_value=mock_voice):
        resp = await client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Hello, world!"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"mp3_chunk_1mp3_chunk_2"


@pytest.mark.asyncio
async def test_synthesize_empty_text(client: AsyncClient, sample_user_data: dict) -> None:
    """Test synthesis with empty text returns 400."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # FastAPI validation returns 422


@pytest.mark.asyncio
async def test_synthesize_too_long(client: AsyncClient, sample_user_data: dict) -> None:
    """Test synthesis with too-long text returns 400."""
    reg_resp = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": "A" * 5001},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # FastAPI validation returns 422


@pytest.mark.asyncio
async def test_synthesize_unauthorized(client: AsyncClient) -> None:
    """Test synthesis without auth returns 401."""
    resp = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Hello"},
    )
    assert resp.status_code == 401
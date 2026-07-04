"""Tests for vision service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.services.vision import VisionService


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Generate a minimal valid PNG for testing."""
    import struct
    import zlib

    # Minimal 1x1 red PNG
    width, height = 1, 1
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"  # filter byte
        for x in range(width):
            raw_data += b"\xff\x00\x00"  # RGB pixel

    def create_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + chunk + crc

    png = b"\x89PNG\r\n\x1a\n"
    png += create_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += create_chunk(b"IDAT", zlib.compress(raw_data))
    png += create_chunk(b"IEND", b"")

    return png


@pytest_asyncio.fixture
async def vision_service() -> VisionService:
    """Create a VisionService instance for testing."""
    return VisionService()


@pytest.mark.asyncio
async def test_analyze_screenshot_no_api_key(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test analyze_screenshot when no API key is set."""
    with patch("app.config.settings.openai_api_key", None):
        with patch.object(vision_service, "_get_client") as mock_get:
            # Simulate API error gracefully
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("No API key configured"),
            )
            mock_get.return_value = mock_client

            result = await vision_service.analyze_screenshot(
                sample_image_bytes,
                prompt="What do you see?",
            )
        assert "description" in result


@pytest.mark.asyncio
async def test_analyze_screenshot_success(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test successful screenshot analysis."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content="I see a red pixel on screen.",
                role="assistant",
            ),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await vision_service.analyze_screenshot(
            sample_image_bytes,
            prompt="What do you see?",
        )

    assert "description" in result
    assert result["model"] == "gpt-4o"
    assert result["processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_describe_screen(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test screen description."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content="This is a screen showing a red background.",
                role="assistant",
            ),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await vision_service.describe_screen(sample_image_bytes)

    assert "description" in result
    assert "screen" in result["description"].lower()


@pytest.mark.asyncio
async def test_find_element_success(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test finding an element on screen."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"found": true, "x": 100, "y": 200, "width": 50, '
                '"height": 30, "confidence": 0.95, "label": "Login Button", '
                '"explanation": "Found the login button in the center of the screen"}',
                role="assistant",
            ),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await vision_service.find_element(
            sample_image_bytes,
            "the login button",
        )

    assert result["found"] is True
    assert result["x"] == 100
    assert result["y"] == 200
    assert result["confidence"] == 0.95
    assert result["label"] == "Login Button"
    assert "explanation" in result


@pytest.mark.asyncio
async def test_find_element_not_found(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test finding a non-existent element."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"found": false, "confidence": 0.0, '
                '"explanation": "Could not find the specified element on screen"}',
                role="assistant",
            ),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await vision_service.find_element(
            sample_image_bytes,
            "non-existent element",
        )

    assert result["found"] is False
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_compare_screenshots(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test comparing two screenshots."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"changes_detected": true, '
                '"description": "The color changed from red to blue"}',
                role="assistant",
            ),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await vision_service.compare_screenshots(
            sample_image_bytes,
            sample_image_bytes,
        )

    assert result["changes_detected"] is True
    assert "description" in result


@pytest.mark.asyncio
async def test_extract_text_regions(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test extracting text regions."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"regions": [{"text": "Hello", "x": 10, "y": 20, '
                '"width": 50, "height": 20, "confidence": 0.9}], '
                '"full_text": "Hello"}',
                role="assistant",
            ),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await vision_service.extract_text_regions(sample_image_bytes)

    assert len(result["regions"]) == 1
    assert result["regions"][0]["text"] == "Hello"
    assert result["full_text"] == "Hello"


@pytest.mark.asyncio
async def test_image_compression(vision_service: VisionService) -> None:
    """Test image compression doesn't fail."""
    # Create a large image using repeated PNG header data
    import io
    import struct
    import zlib

    # Valid 1x1 PNG bytes
    def _make_png_bytes() -> bytes:
        width, height = 1, 1
        raw_data = b"\x00\xff\x00\x00"
        chunk = b"IDAT" + zlib.compress(raw_data)
        crc = struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        idat = struct.pack(">I", len(zlib.compress(raw_data))) + chunk + crc
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr_chunk = b"IHDR" + ihdr_data
        ihdr = struct.pack(">I", 13) + ihdr_chunk + struct.pack(">I", zlib.crc32(ihdr_chunk) & 0xFFFFFFFF)
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
        return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend

    png = _make_png_bytes()
    large_bytes = png * (25 * 1024 * 1024 // len(png) + 1)  # ~25MB
    compressed = vision_service._compress_if_needed(large_bytes)
    assert isinstance(compressed, bytes)


@pytest.mark.asyncio
async def test_cache_hit(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test that cache returns cached result for repeated calls."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(content="Same analysis", role="assistant"),
            delta=None,
        )
    ]
    mock_response.model = "gpt-4o"

    call_count = 0

    async def mock_create(**kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return mock_response

    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = mock_create
        mock_get_client.return_value = mock_client

        # First call
        await vision_service.analyze_screenshot(sample_image_bytes, "test")
        assert call_count == 1

        # Second call with same input should hit cache
        await vision_service.analyze_screenshot(sample_image_bytes, "test")
        assert call_count == 1  # Should not have incremented


@pytest.mark.asyncio
async def test_analyze_screenshot_api_error(
    vision_service: VisionService,
    sample_image_bytes: bytes,
) -> None:
    """Test graceful handling of API errors."""
    with patch.object(vision_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded"),
        )
        mock_get_client.return_value = mock_client

        result = await vision_service.analyze_screenshot(
            sample_image_bytes,
            prompt="What do you see?",
        )

    assert "description" in result
    assert "failed" in result["description"].lower() or "error" in result["description"].lower()


@pytest.mark.asyncio
async def test_lru_cache_eviction() -> None:
    """Test LRU cache eviction when over max size."""
    from app.services.vision import LRUCache

    cache = LRUCache(maxsize=3, ttl=3600)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)

    assert cache.get("a") is None  # Should be evicted
    assert cache.get("b") is not None  # Should still be there
    assert cache.get("d") == 4


@pytest.mark.asyncio
async def test_lru_cache_ttl() -> None:
    """Test LRU cache TTL expiration."""
    import time

    from app.services.vision import LRUCache

    cache = LRUCache(maxsize=10, ttl=0.1)  # 100ms TTL
    cache.set("key", "value")
    assert cache.get("key") == "value"
    time.sleep(0.15)
    assert cache.get("key") is None  # Should be expired
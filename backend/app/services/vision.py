"""Vision service for screenshot analysis using GPT-4o vision."""

from __future__ import annotations

import base64
import io
import time
from collections import OrderedDict
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum image size in bytes before compression
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB

# LRU cache for recent analyses
_CACHE_SIZE = 50
_CACHE_TTL = 60  # seconds


class LRUCache:
    """Simple in-memory LRU cache with TTL."""

    def __init__(self, maxsize: int = _CACHE_SIZE, ttl: int = _CACHE_TTL) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Get a cached value if it exists and hasn't expired."""
        if key not in self._cache:
            return None
        timestamp, value = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a cached value."""
        self._cache[key] = (time.time(), value)
        self._cache.move_to_end(key)
        # Evict oldest if over max size
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


class VisionService:
    """Service for analyzing screenshots using GPT-4o vision capabilities.

    Provides methods for describing screens, finding UI elements,
    comparing screenshots, and extracting text regions.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._cache = LRUCache()

    async def _get_client(self) -> Any:
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 data URL."""
        # Detect format from magic bytes
        if image_bytes[:3] == b"\xff\xd8\xff":
            media_type = "image/jpeg"
        elif image_bytes[:4] == b"\x89PNG":
            media_type = "image/png"
        elif image_bytes[:4] == b"RIFF":
            media_type = "image/webp"
        else:
            media_type = "image/png"

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{media_type};base64,{b64}"

    def _compress_if_needed(self, image_bytes: bytes) -> bytes:
        """Compress image if it exceeds the maximum size."""
        if len(image_bytes) <= MAX_IMAGE_SIZE:
            return image_bytes

        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            # Reduce quality/size iteratively
            quality = 85
            while quality > 10:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if buf.tell() <= MAX_IMAGE_SIZE:
                    return buf.getvalue()
                quality -= 15
            # If still too large, reduce dimensions
            scale = 0.8
            while scale > 0.3:
                w = int(img.width * scale)
                h = int(img.height * scale)
                resized = img.resize((w, h), Image.LANCZOS)
                buf = io.BytesIO()
                resized.save(buf, format="JPEG", quality=60, optimize=True)
                if buf.tell() <= MAX_IMAGE_SIZE:
                    return buf.getvalue()
                scale -= 0.2
            return buf.getvalue()
        except ImportError:
            logger.warning("Pillow not available for image compression — returning original")
            return image_bytes

    async def _call_vision_api(
        self,
        image_bytes: bytes,
        prompt: str,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        """Call the OpenAI vision API with an image and prompt."""
        # Check cache
        cache_key = f"{hash(bytes(image_bytes))}:{prompt}:{response_format or ''}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        image_bytes = self._compress_if_needed(image_bytes)
        image_url = self._encode_image(image_bytes)

        client = await self._get_client()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                ],
            },
        ]

        kwargs: dict[str, Any] = {
            "model": "gpt-4o",
            "messages": messages,
            "max_tokens": 4096,
        }
        if response_format:
            kwargs["response_format"] = {"type": response_format}

        try:
            response = await client.chat.completions.create(**kwargs)
            result = {
                "content": response.choices[0].message.content or "",
                "model": response.model,
            }
            # Cache the result
            self._cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error("Vision API call failed", error=str(e))
            return {
                "content": f"Vision analysis failed: {e!s}",
                "model": "gpt-4o",
                "error": str(e),
            }

    async def analyze_screenshot(
        self,
        image_bytes: bytes,
        prompt: str = "Describe what's on this screen in detail",
    ) -> dict[str, Any]:
        """Analyze a screenshot with a custom prompt."""
        start = time.time()
        result = await self._call_vision_api(image_bytes, prompt)
        elapsed = (time.time() - start) * 1000

        return {
            "description": result.get("content", ""),
            "model": result.get("model", "gpt-4o"),
            "processing_time_ms": round(elapsed, 2),
        }

    async def find_element(
        self,
        image_bytes: bytes,
        description: str,
    ) -> dict[str, Any]:
        """Find a UI element on screen by description."""
        prompt = (
            f"Look at this screenshot carefully. Find the element described as: '{description}'. "
            "Return a JSON object with these fields:\n"
            "- 'found': true/false (whether the element was found)\n"
            "- 'x': the x coordinate of the element's top-left corner (integer)\n"
            "- 'y': the y coordinate of the element's top-left corner (integer)\n"
            "- 'width': the width of the element in pixels (integer)\n"
            "- 'height': the height of the element in pixels (integer)\n"
            "- 'confidence': a number between 0.0 and 1.0 indicating how confident you are\n"
            "- 'label': the text label of the element if it has one\n"
            "- 'explanation': brief explanation of why you identified this element\n\n"
            "Only return valid JSON, no other text."
        )

        start = time.time()
        result = await self._call_vision_api(image_bytes, prompt)
        elapsed = (time.time() - start) * 1000

        content = result.get("content", "{}")

        # Try to parse JSON from the response
        import json as json_module

        try:
            data = json_module.loads(content)
        except (json_module.JSONDecodeError, ValueError):
            # Try to extract JSON from markdown code block
            import re

            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
            if json_match:
                try:
                    data = json_module.loads(json_match.group(1))
                except json_module.JSONDecodeError:
                    data = {"found": False, "explanation": content}
            else:
                data = {"found": False, "explanation": content}

        return {
            "found": data.get("found", False),
            "x": data.get("x"),
            "y": data.get("y"),
            "width": data.get("width"),
            "height": data.get("height"),
            "confidence": data.get("confidence", 0.0),
            "label": data.get("label", ""),
            "explanation": data.get("explanation", content),
        }

    async def describe_screen(self, image_bytes: bytes) -> dict[str, Any]:
        """Get a natural language description of everything visible on screen."""
        return await self.analyze_screenshot(
            image_bytes,
            prompt=(
                "Describe everything visible on this screen in detail. "
                "Include:\n"
                "- What application or website is open\n"
                "- All visible UI elements (buttons, text boxes, menus, icons)\n"
                "- Text content that's readable\n"
                "- Layout and structure\n"
                "- Any notifications, dialogs, or overlays\n\n"
                "Be thorough and specific."
            ),
        )

    async def compare_screenshots(
        self,
        before: bytes,
        after: bytes,
    ) -> dict[str, Any]:
        """Compare two screenshots and describe what changed."""
        before_url = self._encode_image(self._compress_if_needed(before))
        after_url = self._encode_image(self._compress_if_needed(after))

        client = await self._get_client()
        start = time.time()

        prompt = (
            "Compare these two screenshots (before and after). "
            "Describe what changed between them in detail. "
            "Return a JSON object with:\n"
            "- 'changes_detected': true/false\n"
            "- 'description': detailed description of what changed\n\n"
            "Only return valid JSON, no other text."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is the BEFORE screenshot:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": before_url, "detail": "high"},
                    },
                    {"type": "text", "text": "Here is the AFTER screenshot:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": after_url, "detail": "high"},
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ]

        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=4096,
            )
            content = response.choices[0].message.content or "{}"
        except Exception as e:
            logger.error("Vision comparison API call failed", error=str(e))
            content = '{"changes_detected": false, "description": "Comparison failed: ' + str(e) + '"}'

        elapsed = (time.time() - start) * 1000

        import json as json_module
        import re

        try:
            data = json_module.loads(content)
        except json_module.JSONDecodeError:
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
            if json_match:
                try:
                    data = json_module.loads(json_match.group(1))
                except json_module.JSONDecodeError:
                    data = {"changes_detected": False, "description": content}
            else:
                data = {"changes_detected": False, "description": content}

        return {
            "changes_detected": data.get("changes_detected", False),
            "description": data.get("description", content),
            "model": "gpt-4o",
            "processing_time_ms": round(elapsed, 2),
        }

    async def extract_text_regions(self, image_bytes: bytes) -> dict[str, Any]:
        """Identify text regions on screen with coordinates using vision API."""
        prompt = (
            "Look at this screenshot and identify all text regions visible on screen. "
            "Return a JSON object with a 'regions' array where each item has:\n"
            "- 'text': the text content (string)\n"
            "- 'x': x coordinate of top-left corner (integer)\n"
            "- 'y': y coordinate of top-left corner (integer)\n"
            "- 'width': width of the text region in pixels (integer)\n"
            "- 'height': height of the text region in pixels (integer)\n"
            "- 'confidence': how confident you are about this text (0.0 to 1.0)\n\n"
            "Also include a 'full_text' field concatenating all text found.\n\n"
            "Only return valid JSON, no other text."
        )

        start = time.time()
        result = await self._call_vision_api(image_bytes, prompt)
        elapsed = (time.time() - start) * 1000

        content = result.get("content", "{}")

        import json as json_module
        import re

        try:
            data = json_module.loads(content)
        except json_module.JSONDecodeError:
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
            if json_match:
                try:
                    data = json_module.loads(json_match.group(1))
                except json_module.JSONDecodeError:
                    data = {"regions": [], "full_text": content}
            else:
                data = {"regions": [], "full_text": content}

        return {
            "regions": data.get("regions", []),
            "full_text": data.get("full_text", ""),
            "model": result.get("model", "gpt-4o"),
            "processing_time_ms": round(elapsed, 2),
            }
    
    async def find_element_on_screen(
        self,
        screenshot_data: str,
        target_description: str,
    ) -> dict[str, Any]:
        """Find a UI element on screen by description.
        Wrapper for smart tools. Delegates to find_element().
        Args:
            screenshot_data: Base64-encoded screenshot
            target_description: Description of element
        Returns:
            Dict with coordinates and confidence
        """
        import base64 as b64_mod
        image_bytes = b64_mod.b64decode(screenshot_data)
        return await self.find_element(image_bytes, target_description)


# Singleton
_vision_service: VisionService | None = None


def get_vision_service() -> VisionService:
    """Get or create the vision service singleton."""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
"""Vision Service — screen understanding via GPT-4o vision API.

Analyzes screenshots to find UI elements, describe screen content,
and provide coordinates for smart interaction tools.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class VisionService:
    """Service for vision-based screen understanding using GPT-4o."""

    def __init__(self) -> None:
        self._client = self._get_client()

    def _get_client(self) -> Any | None:
        """Get OpenAI client if API key is configured."""
        if settings.openai_api_key:
            try:
                from openai import AsyncOpenAI

                return AsyncOpenAI(api_key=settings.openai_api_key)
            except Exception as e:
                logger.warning("Failed to initialize OpenAI client", error=str(e))
                return None
        logger.warning("OPENAI_API_KEY not set — vision features unavailable")
        return None

    def _encode_screenshot(self, hex_data: str) -> str:
        """Convert hex-encoded screenshot data to base64."""
        try:
            raw_bytes = bytes.fromhex(hex_data)
            return base64.b64encode(raw_bytes).decode("utf-8")
        except (ValueError, TypeError) as e:
            logger.error("Failed to encode screenshot", error=str(e))
            return ""

    async def find_element_on_screen(
        self,
        screenshot_data: str,
        target_description: str,
    ) -> dict[str, Any]:
        """Find coordinates of a UI element on screen.

        Args:
            screenshot_data: Hex-encoded PNG screenshot data.
            target_description: Natural language description of what to find.

        Returns:
            Dict with 'x' and 'y' coordinates, or 'error' message.
        """
        if self._client is None:
            return self._fallback_find_element(target_description)

        base64_image = self._encode_screenshot(screenshot_data)
        if not base64_image:
            return {"error": "Failed to encode screenshot"}

        try:
            response = await self._client.chat.completions.create(
                model=settings.openai_model or "gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a vision analysis AI. Your job is to find "
                            "UI elements on screen based on natural language "
                            "descriptions. You analyze screenshots and return "
                            "the pixel coordinates (x, y) of the requested element."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Find this element on the screen: "
                                    f"'{target_description}'. "
                                    f"Return ONLY a JSON object with x and y "
                                    f"coordinates of where to click. "
                                    f"Format: {{\"x\": 123, \"y\": 456}}. "
                                    f"If you can't find it, return "
                                    f"{{\"error\": \"description of why\"}}."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=300,
                temperature=0.1,
            )

            content = response.choices[0].message.content or ""
            # Try to parse JSON from response
            result = self._parse_json_response(content)
            if result is None:
                return {"error": "Vision API returned unparseable response"}
            return result

        except Exception as e:
            logger.error("Vision API error in find_element", error=str(e))
            return {"error": f"Vision analysis failed: {e!s}"}

    async def describe_screen(
        self,
        screenshot_data: str,
        focus: str | None = None,
    ) -> dict[str, Any]:
        """Describe everything visible on the screen.

        Args:
            screenshot_data: Hex-encoded PNG screenshot data.
            focus: Optional area to focus on (e.g., 'the browser window').

        Returns:
            Dict with 'description', 'elements', and 'text_content' keys.
        """
        if self._client is None:
            return self._fallback_describe(focus)

        base64_image = self._encode_screenshot(screenshot_data)
        if not base64_image:
            return {"error": "Failed to encode screenshot"}

        focus_instruction = (
            f"Focus specifically on: {focus}." if focus else "Describe the entire screen."
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.openai_model or "gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a vision analysis AI. Analyze screenshots "
                            "and describe what's visible in structured detail. "
                            "Return JSON with: description (overview), elements "
                            "(list of visible UI elements with type, text, and "
                            "approximate position), and text_content (all visible text)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Describe what's on this screen. {focus_instruction}"
                                    "Return ONLY valid JSON with this structure:\n"
                                    "{\n"
                                    '  "description": "brief overview of the screen",\n'
                                    '  "elements": [\n'
                                    '    {"type": "button|text|input|icon|window|...", '
                                    '"text": "visible text", '
                                    '"position": "top-left|center|...", '
                                    '"bounds": {"x": 0, "y": 0, "w": 100, "h": 50}}\n'
                                    "  ],\n"
                                    '  "text_content": "all visible text concatenated"\n'
                                    "}"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=1000,
                temperature=0.1,
            )

            content = response.choices[0].message.content or ""
            result = self._parse_json_response(content)

            if result and isinstance(result, dict):
                return result
            return {"description": content, "elements": [], "text_content": ""}

        except Exception as e:
            logger.error("Vision API error in describe_screen", error=str(e))
            return {"error": f"Vision analysis failed: {e!s}"}

    def _parse_json_response(self, content: str) -> dict[str, Any] | None:
        """Parse JSON from LLM response, handling markdown code blocks."""
        content = content.strip()

        # Remove markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last line (``` markers)
            if len(lines) > 2:
                content = "\n".join(lines[1:-1]).strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON within the text
            import re

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return None

    def _fallback_find_element(self, target: str) -> dict[str, Any]:
        """Fallback when vision API is unavailable."""
        logger.warning("Vision API unavailable — providing fallback guidance")
        return {
            "error": (
                f"Cannot find '{target}' on screen — "
                "vision API is not configured (OPENAI_API_KEY required). "
                "Please set the OPENAI_API_KEY environment variable to "
                "enable vision-based UI element detection."
            ),
        }

    def _fallback_describe(self, focus: str | None = None) -> dict[str, Any]:
        """Fallback when vision API is unavailable."""
        logger.warning("Vision API unavailable — providing fallback guidance")
        focus_note = f" focusing on '{focus}'" if focus else ""
        return {
            "description": (
                f"Cannot analyze screen{focus_note} — "
                "vision API is not configured (OPENAI_API_KEY required). "
                "Please set the OPENAI_API_KEY environment variable to "
                "enable screen understanding."
            ),
            "elements": [],
            "text_content": "",
        }

"""What's On Screen Tool — describe everything visible on the user's screen.

Uses vision API to analyze screenshots and return structured descriptions.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.vision import VisionService
from app.tools.base import BaseTool

logger = get_logger(__name__)


class WhatsOnScreenTool(BaseTool):
    """Tool that describes everything visible on the user's screen."""

    def __init__(self) -> None:
        self._vision = VisionService()

    @property
    def name(self) -> str:
        return "whats_on_screen"

    @property
    def description(self) -> str:
        return (
            "Describe everything visible on the user's screen. "
            "Use this when the user asks what's on their screen or "
            "before performing actions that depend on screen state. "
            "Returns structured information about visible windows, "
            "UI elements, text content, and their positions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "Optional area to focus on, e.g. "
                                   "'the browser window', 'the terminal', "
                                   "'the top-right corner'. If omitted, "
                                   "describes the entire screen.",
                },
            },
            "required": [],
        }

    async def execute(  # type: ignore[override]
        self,
        focus: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Take a screenshot and describe what's visible.

        Analyzes the screen via Vision API and returns a structured
        description of visible content.
        """
        _ = kwargs
        logger.info("What's on screen", focus=focus)

        # Step 1: Capture screenshot
        screenshot = await self._capture_screenshot()
        if "error" in screenshot:
            return {"error": f"Failed to capture screenshot: {screenshot['error']}"}

        screenshot_data = screenshot.get("data", "")
        width = screenshot.get("width", 0)
        height = screenshot.get("height", 0)

        # Step 2: Send to Vision API for analysis
        analysis = await self._vision.describe_screen(
            screenshot_data=screenshot_data,
            focus=focus,
        )

        if "error" in analysis:
            return {"error": f"Vision analysis failed: {analysis['error']}"}

        return {
            "status": "analyzed",
            "screen_size": {"width": width, "height": height},
            "focus": focus,
            "analysis": analysis.get("description", ""),
            "elements": analysis.get("elements", []),
            "text_content": analysis.get("text_content", ""),
        }

    async def _capture_screenshot(self) -> dict[str, Any]:
        """Capture a screenshot using ScreenshotTool."""
        from app.tools.screenshot import ScreenshotTool

        st = ScreenshotTool()
        result = await st.execute(operation="capture")
        return result if isinstance(result, dict) else {"error": "Unexpected result type"}

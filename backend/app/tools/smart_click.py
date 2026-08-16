"""Smart Click Tool — find and click UI elements using natural language.

Uses vision API to understand screenshots and MouseTool to execute clicks.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.vision import VisionService
from app.tools.base import BaseTool

logger = get_logger(__name__)


class SmartClickTool(BaseTool):
    """Tool that finds and clicks UI elements described in natural language."""

    def __init__(self) -> None:
        self._vision = VisionService()

    @property
    def name(self) -> str:
        return "smart_click"

    @property
    def description(self) -> str:
        return (
            "Find and click a UI element described in natural language. "
            "E.g. 'click the login button', 'click the search box', "
            "'click the submit button'. Works by analyzing a screenshot "
            "to find the element coordinates, then clicking there."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Description of the UI element to click, "
                                   "e.g. 'the login button', 'the search box'",
                },
                "click_type": {
                    "type": "string",
                    "enum": ["single", "double", "right"],
                    "description": "Type of click (default: single)",
                    "default": "single",
                },
            },
            "required": ["target"],
        }

    async def execute(  # type: ignore[override]
        self,
        target: str,
        click_type: str = "single",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Find and click a UI element.

        Takes a screenshot → analyzes it via Vision API → finds element
        coordinates → uses MouseTool to click.
        """
        _ = kwargs
        logger.info("Smart click", target=target, click_type=click_type)

        # Step 1: Take screenshot
        screenshot = await self._capture_screenshot()
        if "error" in screenshot:
            return {"error": f"Failed to capture screenshot: {screenshot['error']}"}

        # Step 2: Use vision to find element coordinates
        vision_result = await self._vision.find_element_on_screen(
            screenshot_data=screenshot.get("data", ""),
            target_description=target,
        )

        if "error" in vision_result:
            return {"error": f"Could not find '{target}' on screen: {vision_result['error']}"}

        x = vision_result["x"]
        y = vision_result["y"]

        # Step 3: Execute the click using MouseTool
        from app.tools.mouse import MouseTool

        mouse = MouseTool()

        click_op = {
            "single": "click",
            "double": "double_click",
            "right": "click",
        }.get(click_type, "click")

        button = "right" if click_type == "right" else "left"

        click_result = await mouse.execute(
            operation=click_op,
            x=x,
            y=y,
            button=button,
        )

        if "error" in click_result:
            return {"error": f"Click failed: {click_result['error']}"}

        return {
            "status": "clicked",
            "target": target,
            "coordinates": {"x": x, "y": y},
            "click_type": click_type,
            "screenshot_size": {
                "width": screenshot.get("width"),
                "height": screenshot.get("height"),
            },
        }

    async def _capture_screenshot(self) -> dict[str, Any]:
        """Capture a screenshot using ScreenshotTool."""
        from app.tools.screenshot import ScreenshotTool

        st = ScreenshotTool()
        result = await st.execute(operation="capture")
        return result if isinstance(result, dict) else {"error": "Unexpected result type"}

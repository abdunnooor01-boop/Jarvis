"""Smart Type Tool — find text fields and type into them using natural language.

Uses vision API to find form fields on screen, clicks on them, and types text.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.vision import VisionService
from app.tools.base import BaseTool

logger = get_logger(__name__)


class SmartTypeTool(BaseTool):
    """Tool that finds a text field and types into it."""

    def __init__(self) -> None:
        self._vision = VisionService()

    @property
    def name(self) -> str:
        return "smart_type"

    @property
    def description(self) -> str:
        return (
            "Find a text field and type into it. "
            "E.g. \"type 'hello@email.com' into the email field\". "
            "If a target field is specified, takes a screenshot to find it, "
            "clicks to focus, then types. If no target, types at cursor position."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to type into the field",
                },
                "target": {
                    "type": "string",
                    "description": "Description of the target field, e.g. "
                                   "'the email field', 'the search bar'. "
                                   "Optional — if omitted, types at cursor position.",
                },
            },
            "required": ["text"],
        }

    async def execute(  # type: ignore[override]
        self,
        text: str,
        target: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Find a text field and type text into it.

        If target is provided:
          1. Takes a screenshot
          2. Uses Vision API to find the field coordinates
          3. Clicks on the field to focus it
          4. Types the text

        If no target:
          1. Types text at current cursor position
        """
        _ = kwargs
        logger.info("Smart type", text_length=len(text), target=target)

        if target:
            # Step 1: Take screenshot
            screenshot = await self._capture_screenshot()
            if "error" in screenshot:
                return {"error": f"Failed to capture screenshot: {screenshot['error']}"}

            # Step 2: Use vision to find field coordinates
            vision_result = await self._vision.find_element_on_screen(
                screenshot_data=screenshot.get("data", ""),
                target_description=target,
            )

            if "error" in vision_result:
                return {
                    "error": f"Could not find '{target}' on screen: {vision_result['error']}",
                }

            x = vision_result["x"]
            y = vision_result["y"]

            # Step 3: Click on the field to focus it
            from app.tools.mouse import MouseTool

            mouse = MouseTool()
            click_result = await mouse.execute(
                operation="click",
                x=x,
                y=y,
                button="left",
            )

            if "error" in click_result:
                return {"error": f"Failed to focus field: {click_result['error']}"}

            # Step 4: Type the text
            from app.tools.keyboard import KeyboardTool

            keyboard = KeyboardTool()
            type_result = await keyboard.execute(
                operation="type",
                text=text,
            )

            if "error" in type_result:
                return {"error": f"Failed to type text: {type_result['error']}"}

            return {
                "status": "typed",
                "target": target,
                "coordinates": {"x": x, "y": y},
                "text_length": len(text),
            }

        # No target — just type at cursor position
        from app.tools.keyboard import KeyboardTool

        keyboard = KeyboardTool()
        type_result = await keyboard.execute(operation="type", text=text)

        if "error" in type_result:
            return {"error": f"Failed to type text: {type_result['error']}"}

        return {
            "status": "typed",
            "target": None,
            "text_length": len(text),
        }

    async def _capture_screenshot(self) -> dict[str, Any]:
        """Capture a screenshot using ScreenshotTool."""
        from app.tools.screenshot import ScreenshotTool

        st = ScreenshotTool()
        result = await st.execute(operation="capture")
        return result if isinstance(result, dict) else {"error": "Unexpected result type"}

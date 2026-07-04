"""Vision tool — screen understanding via GPT-4o vision."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool


class VisionTool(BaseTool):
    """Tool for analyzing screen content using GPT-4o vision.

    Takes a screenshot, sends it to the vision service, and returns
    structured analysis of what's visible on screen.
    """

    @property
    def name(self) -> str:
        return "screen_vision"

    @property
    def description(self) -> str:
        return (
            "Analyze what's on the user's screen. Use this to understand "
            "UI elements, read content, find specific buttons or fields, "
            "or describe what's visible. Provide a query describing what "
            "you're looking for."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for or analyze on screen, "
                    "e.g. 'find the search box', 'what's in the notification?', "
                    "'describe the current page'",
                },
                "region": {
                    "type": "string",
                    "description": "Optional specific region to analyze, "
                    "e.g. 'top-right corner', 'bottom toolbar'",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        region: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute the vision tool.

        Takes a screenshot and analyzes it with GPT-4o vision.
        """
        _ = kwargs

        try:
            # Capture screenshot using ScreenshotTool
            from app.tools.screenshot import ScreenshotTool

            screenshot_tool = ScreenshotTool()

            if region:
                # Parse region for targeted capture later
                screenshot_result = await screenshot_tool.execute(operation="capture")
            else:
                screenshot_result = await screenshot_tool.execute(operation="capture")

            if "error" in screenshot_result:
                return {
                    "success": False,
                    "error": screenshot_result["error"],
                }

            # Get the image bytes from hex-encoded data
            image_hex = screenshot_result.get("data", "")
            if not image_hex:
                return {
                    "success": False,
                    "error": "No screenshot data available",
                }
            image_bytes = bytes.fromhex(image_hex)

            # Analyze using vision service
            from app.services.vision import get_vision_service

            vision = get_vision_service()

            # Build appropriate prompt based on query
            prompt = f"Look at this screenshot. {query}"

            result = await vision.analyze_screenshot(image_bytes, prompt)

            return {
                "success": True,
                "analysis": result.get("description", ""),
                "width": screenshot_result.get("width"),
                "height": screenshot_result.get("height"),
            }

        except ImportError as e:
            return {
                "success": False,
                "error": f"Vision analysis requires additional dependencies: {e!s}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Vision analysis failed: {e!s}",
            }
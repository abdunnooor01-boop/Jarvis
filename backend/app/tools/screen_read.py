"""Screen reading tool — OCR text from screen."""

from __future__ import annotations

import io
from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class ScreenReadTool(BaseTool):
    """Tool for reading text from the screen via OCR."""

    @property
    def name(self) -> str:
        return "screen_read"

    @property
    def description(self) -> str:
        return "Read text from the screen using OCR. Can read full screen or a specific region."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read_text", "find_text"],
                    "description": "The screen reading operation",
                },
                "text": {
                    "type": "string",
                    "description": "Text to search for (for find_text operation)",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate of region",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate of region",
                },
                "width": {
                    "type": "integer",
                    "description": "Width of region",
                },
                "height": {
                    "type": "integer",
                    "description": "Height of region",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        text: str | None = None,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a screen reading operation."""
        _ = kwargs
        try:
            import pytesseract
            from PIL import Image

            # Capture the screen or region
            if width > 0 and height > 0:
                screenshot = self._capture_region(x, y, width, height)
            else:
                screenshot = self._capture_full()

            if operation == "read_text":
                ocr_text = pytesseract.image_to_string(screenshot)
                lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
                return {"text": ocr_text.strip(), "lines": lines, "line_count": len(lines)}

            elif operation == "find_text":
                if not text:
                    return {"error": "Text is required for find_text operation"}
                ocr_text = pytesseract.image_to_string(screenshot)
                # Try to find the text
                import re
                matches = []
                for i, line in enumerate(ocr_text.split("\n")):
                    if text.lower() in line.lower():
                        # Get approximate position using pytesseract image_to_data
                        try:
                            data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
                            for j, word in enumerate(data["text"]):
                                if text.lower() in word.lower():
                                    matches.append({
                                        "line": i,
                                        "text": word,
                                        "x": data["left"][j],
                                        "y": data["top"][j],
                                        "width": data["width"][j],
                                        "height": data["height"][j],
                                    })
                        except Exception:
                            matches.append({"line": i, "text": line.strip()})
                return {"found": len(matches) > 0, "matches": matches, "count": len(matches)}

            else:
                return {"error": f"Unknown operation: {operation}"}

        except ImportError as e:
            return {"error": f"Screen reading requires pytesseract and Pillow: {e!s}"}
        except Exception as e:
            logger.error("Screen read error", operation=operation, error=str(e))
            return {"error": f"Screen reading failed: {e!s}"}

    def _capture_full(self) -> Any:
        """Capture full screen using PIL."""
        import pyautogui
        return pyautogui.screenshot()

    def _capture_region(self, x: int, y: int, width: int, height: int) -> Any:
        """Capture region using PIL."""
        import pyautogui
        return pyautogui.screenshot(region=(x, y, width, height))
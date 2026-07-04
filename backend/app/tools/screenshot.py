"""Screenshot tool — capture screen or region."""

from __future__ import annotations

import io
from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class ScreenshotTool(BaseTool):
    """Tool for capturing screenshots."""

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return "Capture a screenshot of the full screen or a specific region. Returns PNG image data."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["capture", "capture_region"],
                    "description": "The screenshot operation",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate (for region capture)",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate (for region capture)",
                },
                "width": {
                    "type": "integer",
                    "description": "Width of region (for region capture)",
                },
                "height": {
                    "type": "integer",
                    "description": "Height of region (for region capture)",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a screenshot operation."""
        _ = kwargs
        try:
            if operation == "capture":
                return await self._capture_full()
            elif operation == "capture_region":
                return await self._capture_region(x, y, width, height)
            else:
                return {"error": f"Unknown operation: {operation}"}
        except ImportError:
            return {"error": "Screenshot requires mss or pyautogui (available on desktop)"}
        except Exception as e:
            logger.error("Screenshot error", operation=operation, error=str(e))
            return {"error": f"Screenshot failed: {e!s}"}

    async def _capture_full(self) -> dict[str, Any]:
        """Capture full screen."""
        try:
            import mss

            with mss.mss() as sct:
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                png_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
                return {
                    "width": sct_img.size[0],
                    "height": sct_img.size[1],
                    "format": "png",
                    "size": len(png_bytes),
                    "data": png_bytes.hex(),
                }
        except (ImportError, OSError):
            # Fallback to pyautogui
            import pyautogui

            img = pyautogui.screenshot()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            return {
                "width": img.width,
                "height": img.height,
                "format": "png",
                "size": len(png_bytes),
                "data": png_bytes.hex(),
            }

    async def _capture_region(self, x: int, y: int, width: int, height: int) -> dict[str, Any]:
        """Capture a region of the screen."""
        if width <= 0 or height <= 0:
            return {"error": "Width and height must be positive"}

        try:
            import mss

            with mss.mss() as sct:
                monitor = {"top": y, "left": x, "width": width, "height": height}
                sct_img = sct.grab(monitor)
                png_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
                return {
                    "width": sct_img.size[0],
                    "height": sct_img.size[1],
                    "format": "png",
                    "size": len(png_bytes),
                    "data": png_bytes.hex(),
                }
        except (ImportError, OSError):
            import pyautogui

            img = pyautogui.screenshot(region=(x, y, width, height))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            return {
                "width": img.width,
                "height": img.height,
                "format": "png",
                "size": len(png_bytes),
                "data": png_bytes.hex(),
            }

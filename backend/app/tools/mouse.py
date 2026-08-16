"""Mouse tool — control mouse cursor and clicks."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class MouseTool(BaseTool):
    """Tool for controlling the mouse cursor."""

    @property
    def name(self) -> str:
        return "mouse"

    @property
    def description(self) -> str:
        return "Control the mouse cursor — move, click, double-click, drag, scroll, and get position."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "move", "click", "double_click",
                        "drag", "scroll", "get_position",
                    ],
                    "description": "The mouse operation to perform",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate",
                },
                "x2": {
                    "type": "integer",
                    "description": "End X coordinate (for drag)",
                },
                "y2": {
                    "type": "integer",
                    "description": "End Y coordinate (for drag)",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "description": "Mouse button (default: left)",
                },
                "amount": {
                    "type": "integer",
                    "description": "Scroll amount (positive=up, negative=down)",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        x: int = 0,
        y: int = 0,
        x2: int = 0,
        y2: int = 0,
        button: str = "left",
        amount: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a mouse operation."""
        _ = kwargs
        try:
            import pyautogui

            # Fail-safe: enable pyautogui's built-in safety
            pyautogui.FAILSAFE = True

            if operation == "move":
                pyautogui.moveTo(x, y)
                return {"status": "moved", "x": x, "y": y}

            elif operation == "click":
                pyautogui.click(x, y, button=button)
                return {"status": "clicked", "x": x, "y": y, "button": button}

            elif operation == "double_click":
                pyautogui.doubleClick(x, y)
                return {"status": "double_clicked", "x": x, "y": y}

            elif operation == "drag":
                pyautogui.drag(x2 - x, y2 - y, button=button)
                return {"status": "dragged", "from": {"x": x, "y": y}, "to": {"x": x2, "y": y2}}

            elif operation == "scroll":
                pyautogui.scroll(amount)
                return {"status": "scrolled", "amount": amount}

            elif operation == "get_position":
                pos = pyautogui.position()
                return {"x": pos.x, "y": pos.y}

            else:
                return {"error": f"Unknown operation: {operation}"}

        except ImportError:
            return {"error": "Mouse control requires pyautogui (available on desktop)"}
        except Exception as e:
            logger.error("Mouse error", operation=operation, error=str(e))
            return {"error": f"Mouse operation failed: {e!s}"}
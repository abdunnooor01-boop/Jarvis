"""Keyboard tool — type text and press keys."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class KeyboardTool(BaseTool):
    """Tool for keyboard input — typing, hotkeys, and key presses."""

    @property
    def name(self) -> str:
        return "keyboard"

    @property
    def description(self) -> str:
        return "Type text, press hotkey combinations, or press individual keys."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["type", "hotkey", "press"],
                    "description": "The keyboard operation to perform",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type (for type operation)",
                },
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keys for hotkey combination (e.g. ['ctrl', 'c'])",
                },
                "key": {
                    "type": "string",
                    "description": "Single key to press (for press operation)",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        text: str | None = None,
        keys: list[str] | None = None,
        key: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a keyboard operation."""
        _ = kwargs
        try:
            import pyautogui

            pyautogui.FAILSAFE = True

            if operation == "type":
                if not text:
                    return {"error": "Text is required for type operation"}
                if len(text) > 10000:
                    return {"error": "Text too long (max 10000 characters)"}
                pyautogui.write(text, interval=0.01)
                return {"status": "typed", "length": len(text)}

            elif operation == "hotkey":
                if not keys:
                    return {"error": "Keys list is required for hotkey operation"}
                pyautogui.hotkey(*keys)
                return {"status": "hotkey_pressed", "keys": keys}

            elif operation == "press":
                if not key:
                    return {"error": "Key is required for press operation"}
                pyautogui.press(key)
                return {"status": "key_pressed", "key": key}

            else:
                return {"error": f"Unknown operation: {operation}"}

        except ImportError:
            return {"error": "Keyboard control requires pyautogui (available on desktop)"}
        except Exception as e:
            logger.error("Keyboard error", operation=operation, error=str(e))
            return {"error": f"Keyboard operation failed: {e!s}"}

"""Clipboard tool — read/write system clipboard."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class ClipboardTool(BaseTool):
    """Tool for reading and writing the system clipboard."""

    @property
    def name(self) -> str:
        return "clipboard"

    @property
    def description(self) -> str:
        return "Read from or write to the system clipboard."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write"],
                    "description": "The clipboard operation to perform",
                },
                "text": {
                    "type": "string",
                    "description": "Text to write to clipboard (required for write operation)",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self, operation: str, text: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute a clipboard operation."""
        _ = kwargs
        try:
            import pyperclip

            if operation == "read":
                content = pyperclip.paste()
                return {"content": content, "length": len(content)}

            elif operation == "write":
                if text is None:
                    return {"error": "Text is required for write operation"}
                pyperclip.copy(text)
                return {"status": "written", "length": len(text)}

            else:
                return {"error": f"Unknown operation: {operation}"}

        except ImportError:
            return {"error": "Clipboard access requires pyperclip (available on desktop)"}
        except Exception as e:
            logger.error("Clipboard error", operation=operation, error=str(e))
            return {"error": f"Clipboard operation failed: {e!s}"}
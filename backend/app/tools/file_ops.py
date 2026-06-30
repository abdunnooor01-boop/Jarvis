"""Sandboxed file operations tool."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)

# Restrict file operations to allowed directories
SANDBOX_BASE = Path.home()
ALLOWED_PATHS = [
    SANDBOX_BASE,
    SANDBOX_BASE / "Documents",
    SANDBOX_BASE / "Desktop",
    SANDBOX_BASE / "Downloads",
    Path("/tmp"),
]


class FileOpsTool(BaseTool):
    """Tool for reading and writing files within a sandboxed directory."""

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return (
            "Read and write files in the user's sandbox. "
            "Supports read, write, list, and delete operations."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete"],
                    "description": "The file operation to perform",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory (relative to sandbox)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (only for write operation)",
                },
            },
            "required": ["operation", "path"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        path: str,
        content: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a file operation."""
        _ = kwargs  # Allow extra kwargs for interface compatibility
        resolved = self._resolve_path(path)
        if resolved is None:
            return {"error": f"Access denied: path '{path}' is outside the allowed sandbox"}

        try:
            if operation == "read":
                return await self._read_file(resolved)
            elif operation == "write":
                return await self._write_file(resolved, content or "")
            elif operation == "list":
                return await self._list_dir(resolved)
            elif operation == "delete":
                return await self._delete_file(resolved)
            else:
                return {"error": f"Unknown operation: {operation}"}
        except Exception as e:
            logger.error("File operation error", operation=operation, path=path, error=str(e))
            return {"error": str(e)}

    def _resolve_path(self, path: str) -> Path | None:
        """Resolve a path and check it's within the sandbox."""
        p = Path(path)
        if not p.is_absolute():
            p = SANDBOX_BASE / p

        p = p.resolve()

        # Check if path is within allowed directory
        for allowed in ALLOWED_PATHS:
            try:
                p.relative_to(allowed.resolve())
                return p
            except ValueError:
                continue

        return None

    async def _read_file(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"error": "File not found"}
        if not path.is_file():
            return {"error": "Path is not a file"}

        content = path.read_text(encoding="utf-8")
        return {
            "path": str(path),
            "content": content,
            "size": len(content),
        }

    async def _write_file(self, path: Path, content: str) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "path": str(path),
            "written": len(content),
            "status": "ok",
        }

    async def _list_dir(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"error": "Directory not found"}
        if not path.is_dir():
            return {"error": "Path is not a directory"}

        items = []
        for entry in os.listdir(str(path)):
            full = path / entry
            items.append(
                {
                    "name": entry,
                    "type": "directory" if full.is_dir() else "file",
                    "size": full.stat().st_size if full.is_file() else 0,
                }
            )

        return {"path": str(path), "items": items, "count": len(items)}

    async def _delete_file(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"error": "Path not found"}

        if path.is_file():
            path.unlink()
            return {"path": str(path), "status": "deleted"}
        elif path.is_dir():
            import shutil

            shutil.rmtree(str(path))
            return {"path": str(path), "status": "deleted"}

        return {"error": "Unknown path type"}

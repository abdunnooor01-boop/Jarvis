"""Application launch tool — open/close/list applications."""

from __future__ import annotations

import asyncio
import platform
from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class AppLaunchTool(BaseTool):
    """Tool for launching, closing, and listing applications."""

    @property
    def name(self) -> str:
        return "app_launch"

    @property
    def description(self) -> str:
        return "Launch or close applications, and list running applications."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["open_app", "close_app", "list_running"],
                    "description": "The app operation to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Application name or path to open/close",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute an app launch operation."""
        _ = kwargs
        try:
            if operation == "open_app":
                return await self._open_app(name or "")
            elif operation == "close_app":
                return await self._close_app(name or "")
            elif operation == "list_running":
                return await self._list_running()
            else:
                return {"error": f"Unknown operation: {operation}"}
        except Exception as e:
            logger.error("App launch error", operation=operation, error=str(e))
            return {"error": f"App operation failed: {e!s}"}

    async def _open_app(self, name: str) -> dict[str, Any]:
        """Launch an application."""
        if not name.strip():
            return {"error": "Application name is required"}

        system = platform.system().lower()

        try:
            if system == "darwin":  # macOS
                process = await asyncio.create_subprocess_exec(
                    "open", "-a", name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            elif system == "windows":
                process = await asyncio.create_subprocess_exec(
                    "start", name,
                    shell=True,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:  # Linux
                # Try common launchers
                launchers = ["xdg-open", "gtk-launch", "kioclient5", "exo-open"]
                for launcher in launchers:
                    try:
                        process = await asyncio.create_subprocess_exec(
                            launcher, name,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await asyncio.sleep(0.5)
                        if process.returncode is None or process.returncode == 0:
                            return {"status": "launched", "app": name, "method": launcher}
                    except FileNotFoundError:
                        continue
                # Try running directly
                process = await asyncio.create_subprocess_exec(
                    name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.sleep(0.5)
                if process.returncode is None or process.returncode == 0:
                    return {"status": "launched", "app": name, "method": "direct"}

            _, stderr = await process.communicate()
            if process.returncode != 0:
                return {"error": f"Failed to launch '{name}': {stderr.decode(errors='replace')}"}
            return {"status": "launched", "app": name}

        except FileNotFoundError:
            return {"error": f"Application '{name}' not found"}
        except Exception as e:
            return {"error": f"Failed to launch '{name}': {e!s}"}

    async def _close_app(self, name: str) -> dict[str, Any]:
        """Close an application."""
        if not name.strip():
            return {"error": "Application name is required"}

        system = platform.system().lower()

        try:
            if system == "darwin":  # macOS
                process = await asyncio.create_subprocess_exec(
                    "pkill", "-x", name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            elif system == "windows":
                process = await asyncio.create_subprocess_exec(
                    "taskkill", "/IM", name, "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:  # Linux
                process = await asyncio.create_subprocess_exec(
                    "pkill", "-f", name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )

            _, stderr = await process.communicate()
            if process.returncode != 0:
                return {"error": f"Failed to close '{name}': {stderr.decode(errors='replace')}"}
            return {"status": "closed", "app": name}

        except Exception as e:
            return {"error": f"Failed to close '{name}': {e!s}"}

    async def _list_running(self) -> dict[str, Any]:
        """List running applications."""
        system = platform.system().lower()

        try:
            if system == "darwin":
                process = await asyncio.create_subprocess_exec(
                    "ps", "-eo", "comm=",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            elif system == "windows":
                process = await asyncio.create_subprocess_exec(
                    "tasklist", "/FO", "CSV",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:  # Linux
                process = await asyncio.create_subprocess_exec(
                    "ps", "-eo", "comm=",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                return {"error": f"Failed to list processes: {stderr.decode(errors='replace')}"}

            processes = sorted(set(
                p.strip() for p in stdout.decode().split("\n") if p.strip()
            ))
            return {"processes": processes, "count": len(processes)}

        except Exception as e:
            return {"error": f"Failed to list processes: {e!s}"}

"""Terminal tool — execute shell commands with safety controls."""

from __future__ import annotations

import asyncio
import os
import re
import signal
from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)

# Commands that are always blocked
BLOCKED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "sudo ",
    "su ",
    "chmod 777 ",
    "dd if=",
    "mkfs.",
    "fdisk",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    ":(){ :|:& };:",  # fork bomb
]

# Enhanced safety: patterns that indicate dangerous operations
DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-rf\s+[/~]"),           # Recursive delete from root/home
    re.compile(r"\bchmod\s+777\s+"),              # World-writable permissions
    re.compile(r"\bchown\s+\w+\s+/"),            # Change owner of root
    re.compile(r"\b(wget|curl)\s+.*\||\|\s*(bash|sh|python)"),  # Download and pipe to shell
    re.compile(r"\beval\s+\$?\("),                # eval with subprocess
    re.compile(r"\bexec\s+\w+"),                  # exec replacement
    re.compile(r">\s*/dev/(sda|sdb|sdc|nvme|mmc)"),  # Write to block devices
    re.compile(r"\bmkfs\.\w+"),                   # Filesystem creation
    re.compile(r"\bmount\s+/"),                   # Mount operations on root
    re.compile(r"\bdd\s+if=/dev/"),               # dd from devices
    re.compile(r"\bpasswd\s+\w+"),                # Password changes
    re.compile(r"\bkillall?\s+-9\b"),             # Force kill
]

# Commands known to require explicit confirmation
HIGH_RISK_COMMANDS = [
    "format", "fdisk", "mkfs", "dd", "shutdown",
    "reboot", "init", "telinit",
]

MAX_OUTPUT_SIZE = 1_048_576  # 1MB
DEFAULT_TIMEOUT = 30
MAX_COMMAND_LENGTH = 10_000  # Max command length to prevent abuse


class TerminalTool(BaseTool):
    """Tool for executing shell commands with safety controls."""

    def __init__(self) -> None:
        self._background_processes: dict[int, asyncio.subprocess.Process] = {}

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command and return the output. "
            "Useful for running scripts, file operations, and system tasks. "
            "Dangerous commands (rm -rf /, sudo, shutdown, etc.) are blocked."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["execute", "execute_background", "kill"],
                    "description": "The terminal operation to perform",
                },
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                    "maxLength": MAX_COMMAND_LENGTH,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30,
                },
                "pid": {
                    "type": "integer",
                    "description": "Process ID to kill (for kill operation)",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        command: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        pid: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a terminal operation."""
        _ = kwargs
        try:
            if operation == "execute":
                return await self._execute_command(command or "", timeout)

            elif operation == "execute_background":
                return await self._execute_background(command or "")

            elif operation == "kill":
                return await self._kill_process(pid)

            else:
                return {"error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error("Terminal error", operation=operation, error=str(e))
            return {"error": f"Terminal operation failed: {e!s}"}

    def _is_dangerous(self, command: str) -> str | None:
        """Check if a command is dangerous. Returns reason string or None."""
        cmd_lower = command.lower().strip()

        # Check blocked commands (exact substring)
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return f"Command blocked: contains '{blocked}'"

        # Check dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(cmd_lower):
                return f"Command blocked: pattern '{pattern.pattern}' detected"

        # Check command length
        if len(command) > MAX_COMMAND_LENGTH:
            return f"Command too long ({len(command)} chars, max {MAX_COMMAND_LENGTH})"

        return None

    async def _execute_command(self, command: str, timeout: int) -> dict[str, Any]:
        """Execute a command with timeout and output limits."""
        if not command.strip():
            return {"error": "Empty command"}

        danger = self._is_dangerous(command)
        if danger:
            logger.warning("Blocked dangerous command", command=command[:100], reason=danger)
            return {"error": danger}

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "error": f"Command timed out after {timeout}s",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                }

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Truncate if too large
            if len(stdout_str) > MAX_OUTPUT_SIZE:
                stdout_str = stdout_str[:MAX_OUTPUT_SIZE] + "\n... [truncated]"
            if len(stderr_str) > MAX_OUTPUT_SIZE:
                stderr_str = stderr_str[:MAX_OUTPUT_SIZE] + "\n... [truncated]"

            return {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": process.returncode or 0,
            }

        except OSError as e:
            return {"error": f"Command execution failed: {e!s}"}

    async def _execute_background(self, command: str) -> dict[str, Any]:
        """Execute a command in the background."""
        if not command.strip():
            return {"error": "Empty command"}

        danger = self._is_dangerous(command)
        if danger:
            logger.warning("Blocked dangerous background command", command=command[:100], reason=danger)
            return {"error": danger}

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            pid = process.pid
            self._background_processes[pid] = process
            return {
                "pid": pid,
                "status": "started",
                "message": f"Process {pid} started in background",
            }
        except Exception as e:
            return {"error": f"Failed to start background process: {e!s}"}

    async def _kill_process(self, pid: int | None) -> dict[str, Any]:
        """Kill a process by PID."""
        if pid is None:
            return {"error": "PID is required for kill operation"}

        try:
            os.kill(pid, signal.SIGTERM)
            # Remove from our tracking if it was backgrounded by us
            self._background_processes.pop(pid, None)
            return {"pid": pid, "status": "terminated"}
        except ProcessLookupError:
            return {"error": f"Process {pid} not found"}
        except PermissionError:
            return {"error": f"Permission denied to kill process {pid}"}
        except Exception as e:
            return {"error": f"Failed to kill process {pid}: {e!s}"}
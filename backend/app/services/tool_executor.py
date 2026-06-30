"""Tool execution engine — dispatches tool calls to registered tools."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool
from app.tools.file_ops import FileOpsTool
from app.tools.web_search import WebSearchTool

logger = get_logger(__name__)


class ToolExecutor:
    """Receives tool call requests and dispatches to registered tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register built-in tools."""
        self.register(WebSearchTool())
        self.register(FileOpsTool())
        logger.info("Default tools registered", count=len(self._tools))

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions for all registered tools."""
        return [tool.to_openai_definition() for tool in self._tools.values()]

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call and return the result."""
        tool = self._tools.get(tool_name)
        if tool is None:
            logger.warning("Tool not found", tool_name=tool_name)
            return {"error": f"Tool '{tool_name}' not found"}

        logger.info("Executing tool", tool_name=tool_name, arguments=arguments)
        try:
            result = await tool.execute(**arguments)
            return {"result": result}
        except Exception as e:
            logger.error("Tool execution error", tool_name=tool_name, error=str(e))
            return {"error": f"Tool execution failed: {e!s}"}
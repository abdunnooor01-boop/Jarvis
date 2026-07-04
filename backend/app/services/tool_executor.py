"""Tool execution engine — dispatches tool calls to registered tools."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool
from app.tools.file_ops import FileOpsTool
from app.tools.web_search import WebSearchTool
from app.tools.clipboard import ClipboardTool
from app.tools.terminal import TerminalTool
from app.tools.screenshot import ScreenshotTool
from app.tools.screen_read import ScreenReadTool
from app.tools.mouse import MouseTool
from app.tools.keyboard import KeyboardTool
from app.tools.app_launch import AppLaunchTool
from app.tools.browser import BrowserTool
from app.tools.vision_tool import VisionTool

logger = get_logger(__name__)


class ToolExecutor:
    """Receives tool call requests and dispatches to registered tools."""

    _plugins_loaded = False
    _plugin_tools: dict[str, BaseTool] = {}

    @classmethod
    async def preload_plugins(cls) -> None:
        """Preload plugins asynchronously during application startup."""
        if not cls._plugins_loaded:
            logger.info("Preloading plugins during startup...")
            from app.services.plugin_loader import PluginLoader

            # Create a temporary executor that skips plugins to avoid recursion
            executor = cls(skip_plugins=True)
            loader = PluginLoader()
            await loader.load_plugins(executor)

            # Save only the plugin tools
            cls._plugin_tools = {
                name: tool
                for name, tool in executor._tools.items()
                if name not in executor._default_tool_names
            }
            cls._plugins_loaded = True
            logger.info("Plugins preloaded successfully", count=len(cls._plugin_tools))

    def __init__(self, skip_plugins: bool = False) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools()
        self._default_tool_names = set(self._tools.keys())

        if not skip_plugins and self._plugins_loaded:
            self._tools.update(self._plugin_tools)
            logger.info("Plugin tools loaded from preload cache", count=len(self._plugin_tools))

    def _register_default_tools(self) -> None:
        """Register built-in tools."""
        self.register(WebSearchTool())
        self.register(FileOpsTool())
        self.register(ClipboardTool())
        self.register(TerminalTool())
        self.register(ScreenshotTool())
        self.register(ScreenReadTool())
        self.register(MouseTool())
        self.register(KeyboardTool())
        self.register(AppLaunchTool())
        self.register(BrowserTool())
        self.register(VisionTool())
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

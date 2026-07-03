"""Plugin loader for dynamically discovering and loading plugins."""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import select

from app.config import settings
from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.plugin import Plugin
from app.plugin_system.plugin_manifest import PluginManifest
from app.tools.base import BaseTool

logger = get_logger(__name__)

# A list of dangerous modules to block
DANGEROUS_MODULES = {
    "os",
    "subprocess",
    "shutil",
    "sys",
    "ctypes",
    "socket",
    "urllib",
    "requests",
    "platform",
}


class RestrictedImportError(ImportError):
    """Raised when a plugin tries to import a forbidden module."""
    pass


@contextlib.contextmanager
def sandboxed_context():
    """Context manager that overrides __import__ to block dangerous modules."""
    original_import = builtins.__import__

    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        parts = name.split(".")
        for part in parts:
            if part in DANGEROUS_MODULES:
                raise RestrictedImportError(
                    f"Import of module '{part}' is restricted for security."
                )
        if fromlist:
            for f in fromlist:
                if f in DANGEROUS_MODULES:
                    raise RestrictedImportError(
                        f"Import of '{f}' from '{name}' is restricted."
                    )
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = restricted_import
    try:
        yield
    finally:
        builtins.__import__ = original_import


class PluginToolWrapper(BaseTool):
    """Wraps a plugin tool to enforce prefixes, timeouts, and sandboxing."""

    def __init__(self, original_tool: BaseTool, plugin_name: str, timeout: float = 10.0):
        self.original_tool = original_tool
        self.plugin_name = plugin_name
        self.timeout = timeout
        self._prefixed_name = f"{plugin_name}_{original_tool.name}"

    @property
    def name(self) -> str:
        return self._prefixed_name

    @property
    def description(self) -> str:
        return self.original_tool.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self.original_tool.parameters

    async def execute(self, **kwargs: Any) -> Any:
        try:
            with sandboxed_context():
                result = await asyncio.wait_for(
                    self.original_tool.execute(**kwargs), timeout=self.timeout
                )
                return result
        except asyncio.TimeoutError:
            return (
                f"Error: Tool execution in plugin '{self.plugin_name}' "
                f"timed out after {self.timeout}s."
            )
        except RestrictedImportError as e:
            return f"Security Error: Plugin '{self.plugin_name}' attempted a forbidden action: {e}"
        except Exception as e:
            return f"Error: Plugin '{self.plugin_name}' tool execution failed: {type(e).__name__}: {e}"


class PluginLoader:
    """Discovers, validates, and loads plugins and their tools."""

    def __init__(self, plugins_dir: str | Path | None = None) -> None:
        self.plugins_dir = Path(plugins_dir or settings.plugins_dir)
        self.manifests: Dict[str, PluginManifest] = {}
        self.tools: Dict[str, List[BaseTool]] = {}

    def load_manifest(self, plugin_dir: Path) -> Optional[PluginManifest]:
        """Loads and validates a plugin manifest (YAML or JSON)."""
        yaml_path = plugin_dir / "plugin.yaml"
        json_path = plugin_dir / "plugin.json"

        manifest_data = None
        try:
            if yaml_path.is_file():
                with open(yaml_path, "r", encoding="utf-8") as f:
                    manifest_data = yaml.safe_load(f)
            elif json_path.is_file():
                with open(json_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            else:
                return None

            if manifest_data:
                return PluginManifest(**manifest_data)
        except Exception as e:
            logger.error(
                "Failed to load/validate manifest",
                plugin_dir=plugin_dir.name,
                error=str(e),
            )
        return None

    def discover_plugins(self) -> List[Path]:
        """Scans the plugins directory for subdirectories containing a manifest."""
        plugin_dirs = []
        if not self.plugins_dir.exists():
            return []

        for item in self.plugins_dir.iterdir():
            if item.is_dir():
                if (item / "plugin.yaml").is_file() or (item / "plugin.json").is_file():
                    plugin_dirs.append(item)
        return plugin_dirs

    def load_plugin_modules(self, plugin_dir: Path, manifest: PluginManifest) -> List[BaseTool]:
        """Dynamically imports Python modules from a plugin and finds BaseTool implementations."""
        loaded_tools: List[BaseTool] = []
        plugin_name = manifest.name

        # Find all Python files in the plugin directory
        py_files = list(plugin_dir.rglob("*.py"))

        with sandboxed_context():
            for py_file in py_files:
                if py_file.name == "__init__.py" and py_file.parent == plugin_dir:
                    continue

                module_name = f"app.plugins.{plugin_dir.name}.{py_file.stem}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # Find all classes inheriting from BaseTool
                    for name, value in vars(module).items():
                        if (
                            isinstance(value, type)
                            and issubclass(value, BaseTool)
                            and value is not BaseTool
                            and value.__module__ == module_name
                        ):
                            try:
                                tool_instance = value()
                                loaded_tools.append(tool_instance)
                                logger.info(
                                    "Discovered tool in plugin",
                                    plugin=plugin_name,
                                    tool_name=tool_instance.name,
                                )
                            except Exception as inst_err:
                                logger.error(
                                    "Failed to instantiate tool",
                                    plugin=plugin_name,
                                    tool_class=name,
                                    error=str(inst_err),
                                )
                except Exception as load_err:
                    logger.error(
                        "Failed to load module", file=str(py_file), error=str(load_err)
                    )

        return loaded_tools

    async def sync_plugins_with_db(self, discovered_manifests: List[PluginManifest]) -> List[str]:
        """Sync discovered plugins with the DB, enabling/disabling or registering them."""
        enabled_plugin_names: List[str] = []

        async with async_session_factory() as session:
            try:
                result = await session.execute(select(Plugin))
                db_plugins = {p.name: p for p in result.scalars().all()}

                for manifest in discovered_manifests:
                    if manifest.name in db_plugins:
                        db_plugin = db_plugins[manifest.name]
                        db_plugin.version = manifest.version
                        db_plugin.description = manifest.description
                        db_plugin.author = manifest.author
                        if db_plugin.enabled:
                            enabled_plugin_names.append(manifest.name)
                    else:
                        new_plugin = Plugin(
                            name=manifest.name,
                            version=manifest.version,
                            description=manifest.description,
                            author=manifest.author,
                            enabled=True,
                        )
                        session.add(new_plugin)
                        enabled_plugin_names.append(manifest.name)

                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Database sync failed for plugins", error=str(e))
                enabled_plugin_names = [m.name for m in discovered_manifests]

        return enabled_plugin_names

    async def load_plugins(self, tool_executor: Any) -> None:
        """Discovers, registers with DB, and loads enabled plugins into the ToolExecutor."""
        plugin_dirs = self.discover_plugins()
        discovered_manifests: List[PluginManifest] = []
        dir_to_manifest = {}

        for p_dir in plugin_dirs:
            manifest = self.load_manifest(p_dir)
            if manifest:
                discovered_manifests.append(manifest)
                dir_to_manifest[p_dir] = manifest
                self.manifests[manifest.name] = manifest

        enabled_plugin_names = await self.sync_plugins_with_db(discovered_manifests)

        for p_dir, manifest in dir_to_manifest.items():
            if manifest.name not in enabled_plugin_names:
                logger.info("Skipping disabled plugin", plugin=manifest.name)
                continue

            logger.info("Loading plugin", plugin=manifest.name)
            try:
                original_tools = self.load_plugin_modules(p_dir, manifest)
                wrapped_tools = []
                for tool in original_tools:
                    wrapped = PluginToolWrapper(tool, plugin_name=manifest.name)
                    tool_executor.register(wrapped)
                    wrapped_tools.append(wrapped)

                self.tools[manifest.name] = original_tools
                logger.info(
                    "Successfully loaded plugin tools",
                    plugin=manifest.name,
                    count=len(wrapped_tools),
                )
            except Exception as e:
                logger.error(
                    "Failed to load plugin package", plugin=manifest.name, error=str(e)
                )

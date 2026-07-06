#!/usr/bin/env python3
"""Jarvis Plugin Scaffolding Tool.

Creates a new plugin directory with the standard structure:

    plugins/<plugin-name>/
        plugin.yaml          -- Manifest file
        __init__.py           -- Plugin package init
        tools/                -- Tool implementations
            <tool_name>.py    -- Example tool

Usage:
    python scripts/create-plugin.py my-plugin
    python scripts/create-plugin.py my-plugin --author "Your Name" --description "Does cool things"
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# ---------------------------------------------------------------------------
# Templates (as module-level constants)
# ---------------------------------------------------------------------------

PLUGIN_YAML_TEMPLATE = """\
name: {plugin_name}
version: 1.0.0
description: {description}
author: {author}
tools:
  - name: {tool_name}
    description: A description of what this tool does.
    parameters:
      type: object
      properties:
        query:
          type: string
          description: The input for this tool.
          default: ""
      required: []
"""

INIT_PY_TEMPLATE = (
    '"""%s Plugin."""\n'
)

TOOL_TEMPLATE = '''\
"""%(name)s tool for the %(plugin)s plugin."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool


class %(class)s(BaseTool):
    """Tool that %(desc)s."""

    @property
    def name(self) -> str:
        return "%(name)s"

    @property
    def description(self) -> str:
        return "A description of what this tool does."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The input for this tool.",
                    "default": "",
                }
            },
            "required": [],
        }

    async def execute(self, query: str = "") -> str:
        """Implement your tool logic here."""
        return f"%(plugin)s tool executed with query: {query}"
'''

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLUGIN_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "backend", "app", "plugins")
)


def validate_plugin_name(name: str) -> str:
    """Check that *name* is a valid plugin identifier.

    Returns the validated name on success, or raises ``ValueError``.
    """
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9-]*$", name):
        raise ValueError(
            f"Invalid plugin name {name!r}. "
            "Must start with a letter and contain only alphanumeric characters and hyphens."
        )
    if len(name) < 2:
        raise ValueError(
            f"Invalid plugin name {name!r}. "
            "Must be at least 2 characters long."
        )
    if len(name) > 64:
        raise ValueError(
            f"Invalid plugin name {name!r}. "
            "Must be at most 64 characters long."
        )
    return name


def to_snake_case(name: str) -> str:
    """Convert a kebab-case plugin name to snake_case for tool/class use."""
    return name.replace("-", "_")


def to_pascal_case(name: str) -> str:
    """Convert a kebab-case name to PascalCase."""
    parts = [p.capitalize() for p in name.replace("-", "_").split("_")]
    return "".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def create_plugin(
    plugin_name: str,
    author: str = "Jarvis Developer",
    description: str | None = None,
    tools: list[dict[str, str]] | None = None,
    output_dir: str | None = None,
) -> str:
    """Create a new plugin directory and return its path.

    Parameters
    ----------
    plugin_name:
        Validated plugin identifier (alphanumeric + hyphens).
    author:
        Plugin author name.
    description:
        Short description of the plugin's purpose.
    tools:
        List of tool dicts with keys ``name`` and ``description``.
        If ``None``, a single default tool is created.
    output_dir:
        Directory where the plugin folder will be created.
        Defaults to the standard plugins directory.
    """
    if description is None:
        description = f"A Jarvis plugin that provides {plugin_name.replace('-', ' ')} utilities."

    if tools is None:
        snake_name = to_snake_case(plugin_name)
        tools = [
            {
                "name": f"{snake_name}_tool",
                "description": f"A default tool for the {plugin_name} plugin.",
            }
        ]

    output_dir = output_dir or PLUGIN_DIR
    plugin_path = os.path.join(output_dir, plugin_name)
    tools_dir = os.path.join(plugin_path, "tools")

    # --- Create directories ---
    os.makedirs(tools_dir, exist_ok=True)

    # --- Write plugin.yaml ---
    with open(os.path.join(plugin_path, "plugin.yaml"), "w") as f:
        f.write(
            PLUGIN_YAML_TEMPLATE.format(
                plugin_name=plugin_name,
                description=description,
                author=author,
                tool_name=tools[0]["name"],
            ).lstrip("\n")
        )

    # --- Write __init__.py ---
    with open(os.path.join(plugin_path, "__init__.py"), "w") as f:
        f.write(INIT_PY_TEMPLATE % plugin_name.capitalize())

    # --- Write tool files ---
    for tool in tools:
        tool_name = tool["name"]
        tool_class_name = to_pascal_case(tool_name)
        tool_description_small = tool.get("description", "performs an operation").rstrip(".")

        with open(os.path.join(tools_dir, f"{tool_name}.py"), "w") as f:
            f.write(
                TOOL_TEMPLATE % {
                    "name": tool_name,
                    "plugin": plugin_name,
                    "class": tool_class_name,
                    "desc": tool_description_small,
                }
            )

    return plugin_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new Jarvis plugin scaffold.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "name",
        help="Plugin name (alphanumeric + hyphens, e.g. 'my-plugin').",
    )
    parser.add_argument(
        "--author",
        default="Jarvis Developer",
        help="Plugin author name (default: 'Jarvis Developer').",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Short description of the plugin (default: inferred from name).",
    )
    parser.add_argument(
        "--tool",
        action="append",
        nargs=2,
        metavar=("TOOL_NAME", "TOOL_DESCRIPTION"),
        help="Add a tool (name and description). Can be specified multiple times. "
             "Default: one tool named '<plugin_snake>_tool'.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: backend/app/plugins/).",
    )

    args = parser.parse_args()

    # Validate plugin name
    try:
        plugin_name = validate_plugin_name(args.name)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Tools
    tools = None
    if args.tool:
        tools = [{"name": t[0], "description": t[1]} for t in args.tool]

    # Create
    try:
        plugin_path = create_plugin(
            plugin_name=plugin_name,
            author=args.author,
            description=args.description,
            tools=tools,
            output_dir=args.output,
        )
    except Exception as exc:
        print(f"Error: Failed to create plugin: {exc}", file=sys.stderr)
        sys.exit(1)

    # Summary
    print(f"Plugin '{plugin_name}' created at:")
    print(f"   {plugin_path}/")
    print()
    print("   Files created:")
    for root, _dirs, files in os.walk(plugin_path):
        for fname in sorted(files):
            rel = os.path.relpath(os.path.join(root, fname), plugin_path)
            print(f"   + {rel}")
    print()
    print("   Next steps:")
    print("   1. Edit plugin.yaml to configure your plugin.")
    print("   2. Implement your tool logic in tools/.")
    print("   3. Restart Jarvis to load the new plugin.")


if __name__ == "__main__":
    main()

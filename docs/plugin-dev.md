# Jarvis Plugin Development Guide

This guide covers how to create plugins for Jarvis. Plugins extend Jarvis with custom tools
that can be used by the AI assistant during conversations and task execution.

---

## Quick Start

Create a new plugin scaffold using the CLI tool:

```bash
python scripts/create-plugin.py my-cool-plugin
```

This creates:

```
backend/app/plugins/my-cool-plugin/
├── plugin.yaml            # Plugin manifest
├── __init__.py            # Package init
└── tools/
    └── my_cool_plugin_tool.py   # Example tool
```

Edit the generated files and restart Jarvis to load your plugin.

### Customising the scaffold

```bash
# Specify an author and description
python scripts/create-plugin.py weather-checker \
    --author "Your Name" \
    --description "Provides current weather data for any location"

# Add custom tools (name, description pairs)
python scripts/create-plugin.py file-tools \
    --tool count_lines "Count the number of lines in a file" \
    --tool list_files "List files in a directory matching a pattern"
```

---

## Plugin Structure

Every Jarvis plugin is a directory under `backend/app/plugins/` with this layout:

```
plugins/<plugin-name>/
├── plugin.yaml         # Required — manifest file
├── __init__.py         # Required — can be empty
├── tools/              # Required — tool implementations
│   ├── tool_one.py
│   └── tool_two.py
└── assets/             # Optional — bundled assets
```

---

## Manifest Format (`plugin.yaml`)

The manifest is a YAML file that describes your plugin and its tools.

```yaml
name: my-plugin                    # Required — unique identifier (alphanumeric + hyphens)
version: 1.0.0                     # Required — semver
description: Does cool things.     # Required — short description
author: Your Name                  # Optional — your name/handle
tools:                             # Required — at least one tool
  - name: my_tool                  # Required — snake_case tool name
    description: What it does.     # Required — used by the LLM to decide when to call it
    parameters:                    # Required — JSON Schema for tool inputs
      type: object
      properties:
        query:
          type: string
          description: The input.
          default: ""
      required: []
```

### Manifest schema reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Unique plugin identifier. Must match the directory name. |
| `version` | string | ✅ | Semantic version (e.g., `1.0.0`, `2.3.1`). |
| `description` | string | ✅ | What the plugin does. Displayed in the plugin list. |
| `author` | string | ❌ | Plugin creator name or handle. |
| `tools` | list | ✅ | Array of tool definitions (see below). |

### Tool definition reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Tool name in `snake_case`. Used by the LLM to invoke the tool. |
| `description` | string | ✅ | What the tool does. The LLM uses this to decide when to call it. Be specific. |
| `parameters` | object | ✅ | [JSON Schema](https://json-schema.org/) defining the tool's input parameters. |

---

## Tool API Reference

Each tool is a Python class that extends `BaseTool` and implements four members:

### Required members

```python
from app.tools.base import BaseTool

class MyCoolTool(BaseTool):
    @property
    def name(self) -> str:
        """Tool name in snake_case. Must match the manifest's tool name."""
        return "my_cool_tool"

    @property
    def description(self) -> str:
        """Description used by the LLM to decide when to call this tool."""
        return "Does something cool with the provided input."

    @property
    def parameters(self) -> dict:
        """JSON Schema for tool parameters. Must match the manifest."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The input to process.",
                }
            },
            "required": ["query"],
        }

    async def execute(self, query: str) -> str:
        """Core tool logic. Parameters must match the JSON Schema above."""
        return f"Processed: {query}"
```

### Rules

1. **Parameter names** in `execute()` **must match** the keys in `parameters` JSON Schema.
2. **Default values** in `parameters` JSON Schema (e.g. `"default": "UTC"`) make the parameter optional
   in the method signature.
3. **Return type** should be `str`, `dict`, or a Pydantic model. Strings are preferred for LLM consumption.
4. **Async** — the `execute` method is `async def`. Use `await` for any I/O.
5. **Imports** — use standard library dependencies when possible. For third-party packages, add them to
   `backend/requirements.txt`.

### Full example

See `backend/app/plugins/example-time-plugin/` for a complete, working plugin:

```python
"""Time tool for the example-time-plugin."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import zoneinfo

from app.tools.base import BaseTool


class GetCurrentTimeTool(BaseTool):
    """Tool that returns the current time in a given timezone."""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "Get the current time in a specified timezone (e.g., UTC, America/New_York, Asia/Tokyo)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "The timezone to query (e.g., UTC, America/New_York, Asia/Tokyo).",
                    "default": "UTC",
                }
            },
            "required": [],
        }

    async def execute(self, timezone: str = "UTC") -> str:
        try:
            tz = zoneinfo.ZoneInfo(timezone)
            now = datetime.now(tz)
            return f"The current time in {timezone} is {now.strftime('%Y-%m-%d %H:%M:%S')}"
        except zoneinfo.ZoneInfoNotFoundError:
            tz = zoneinfo.ZoneInfo("UTC")
            now = datetime.now(tz)
            return (
                f"Timezone '{timezone}' was not recognized. "
                f"Falling back to UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
```

---

## Sandboxing & Security

Plugins run in the same Python process as Jarvis, with the following restrictions:

### ✅ Allowed
- Standard library access
- Reading files from the plugin's own directory
- Making HTTP requests (if the tool implements them)
- Using any dependency listed in `requirements.txt`

### ❌ Blocked / Restricted
- **System commands**: `subprocess`, `os.system`, `shutil` operations outside the plugin directory
- **Arbitrary file writes**: Only the plugin's own directory can be written to
- **Network binds**: Plugins cannot open listening sockets
- **Plugin imports**: Plugins cannot import from other plugins
- **Module mutilation**: Plugins cannot modify `sys.path`, `sys.modules`, or monkey-patch core classes

### Best practices
1. Validate all user inputs — don't pass raw strings to `subprocess` or `eval`
2. Use timeouts for any network requests
3. Keep plugin state in-memory or in the plugin's own directory
4. Log errors via `print()` or `logging` (logs appear in the Jarvis server log)

---

## Testing Your Plugin

### Manual testing
1. Place your plugin in `backend/app/plugins/<name>/`
2. Restart the Jarvis server
3. Check the server logs for "Loaded plugin" messages
4. Send a chat message that triggers your tool

### Using the validation API

```bash
curl -X POST http://localhost:8000/api/v1/dev/plugin-validate \
  -H "Content-Type: application/json" \
  -d '{"path": "backend/app/plugins/my-plugin"}'
```

Or validate manifest content directly:

```bash
curl -X POST http://localhost:8000/api/v1/dev/plugin-validate \
  -H "Content-Type: application/json" \
  -d '{"manifest": {"name": "test", "version": "1.0.0", "description": "A test", "tools": [...]}}'
```

### Automated testing
Write pytest tests for your plugin tools:

```python
import pytest
from my_plugin.tools.my_tool import MyTool

@pytest.mark.asyncio
async def test_my_tool():
    tool = MyTool()
    result = await tool.execute(query="hello")
    assert "hello" in result
```

---

## Publishing to the Marketplace

> **Not yet available.** The plugin marketplace is on the roadmap. When ready, you'll be able to
> publish your plugin by pushing it to a GitHub repository and registering it with Jarvis.

For now, share plugins by sharing the plugin directory or publishing it as a GitHub repo.

---

## Troubleshooting

| Problem | Likely cause | Solution |
|---------|-------------|----------|
| Plugin not loaded | Directory structure wrong | Ensure `plugin.yaml`, `__init__.py`, and `tools/` exist |
| "Tool not found" | Name mismatch | Check `tool.name` matches in both `plugin.yaml` and the class |
| LLM never calls my tool | Description too vague | Make the description specific about when the tool should be used |
| ImportError | Missing dependency | Add the package to `backend/requirements.txt` |
| Validation fails | Manifest schema broken | Run `/api/v1/dev/plugin-validate` for detailed errors |

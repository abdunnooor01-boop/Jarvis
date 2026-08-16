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
            # Fallback to UTC if timezone is not recognized
            tz = zoneinfo.ZoneInfo("UTC")
            now = datetime.now(tz)
            return (
                f"Timezone '{timezone}' was not recognized. "
                f"Falling back to UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )

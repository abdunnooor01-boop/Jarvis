"""Abstract base class for tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class that all tools must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (snake_case, used for dispatching)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments."""
        ...

    def to_openai_definition(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

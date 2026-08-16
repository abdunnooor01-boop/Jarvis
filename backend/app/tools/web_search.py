"""Web search tool using Tavily API (or fallback mock)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """Tool that performs web searches using the Tavily API."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information. "
            "Use this to find recent news, facts, or data."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(  # type: ignore[override]
        self, query: str, max_results: int = 5, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute a web search."""
        _ = kwargs  # Allow extra kwargs for interface compatibility
        if settings.tavily_api_key:
            return await self._search_tavily(query, max_results)

        logger.warning("No Tavily API key configured, returning mock results")
        return self._mock_results(query)

    async def _search_tavily(self, query: str, max_results: int) -> dict[str, Any]:
        """Search via Tavily API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": min(max_results, 10),
                        "include_answer": True,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "answer": data.get("answer", ""),
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "content": r.get("content", ""),
                        }
                        for r in data.get("results", [])
                    ],
                }
        except Exception as e:
            logger.error("Tavily search error", error=str(e))
            return {"error": f"Search failed: {e!s}", "results": []}

    def _mock_results(self, query: str) -> dict[str, Any]:
        """Return mock search results when no API key is configured."""
        return {
            "answer": f"Search is not available — no Tavily API key configured. Query was: {query}",
            "results": [
                {
                    "title": "Search unavailable",
                    "url": "",
                    "content": "Configure TAVILY_API_KEY in your environment to enable web search.",
                }
            ],
        }

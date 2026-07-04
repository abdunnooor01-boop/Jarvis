"""Browser tool — open URLs, search, and navigate."""

from __future__ import annotations

import webbrowser
from typing import Any
from urllib.parse import quote_plus

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger(__name__)


class BrowserTool(BaseTool):
    """Tool for browser control — opening URLs, searching, and navigating."""

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Open URLs in the browser, search the web, or navigate (back/forward/refresh)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["open_url", "search", "navigate"],
                    "description": "The browser operation to perform",
                },
                "url": {
                    "type": "string",
                    "description": "URL to open (for open_url operation)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search operation)",
                },
                "action": {
                    "type": "string",
                    "enum": ["back", "forward", "refresh"],
                    "description": "Navigation action (for navigate operation)",
                },
            },
            "required": ["operation"],
        }

    async def execute(  # type: ignore[override]
        self,
        operation: str,
        url: str | None = None,
        query: str | None = None,
        action: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a browser operation."""
        _ = kwargs
        try:
            if operation == "open_url":
                return await self._open_url(url or "")
            elif operation == "search":
                return await self._search(query or "")
            elif operation == "navigate":
                return await self._navigate(action or "")
            else:
                return {"error": f"Unknown operation: {operation}"}
        except Exception as e:
            logger.error("Browser error", operation=operation, error=str(e))
            return {"error": f"Browser operation failed: {e!s}"}

    async def _open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the browser."""
        if not url.strip():
            return {"error": "URL is required"}

        # Add https:// if no scheme provided
        if not url.startswith(("http://", "https://", "file://", "about:")):
            url = "https://" + url

        try:
            # Try Playwright first for more control
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=False)
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    title = await page.title()
                    await browser.close()
                    return {"status": "opened", "url": url, "title": title}
            except Exception:
                # Fallback to webbrowser module
                webbrowser.open(url)
                return {"status": "opened", "url": url, "method": "webbrowser"}

        except Exception as e:
            return {"error": f"Failed to open URL: {e!s}"}

    async def _search(self, query: str) -> dict[str, Any]:
        """Search the web using Google."""
        if not query.strip():
            return {"error": "Search query is required"}

        encoded = quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded}"
        return await self._open_url(search_url)

    async def _navigate(self, action: str) -> dict[str, Any]:
        """Perform a browser navigation action."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()

                if action == "back":
                    await page.go_back()
                elif action == "forward":
                    await page.go_forward()
                elif action == "refresh":
                    await page.reload()
                else:
                    await browser.close()
                    return {"error": f"Unknown navigation action: {action}"}

                title = await page.title()
                url = page.url
                await browser.close()
                return {"status": action, "url": url, "title": title}

        except Exception as e:
            return {"error": f"Navigation failed: {e!s}"}

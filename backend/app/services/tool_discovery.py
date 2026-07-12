"""ToolDiscovery service — discovers new tools from knowledge entries.

Scans knowledge entries for mentions of tools, APIs, or frameworks that
Jarvis could potentially use. Keeps it conservative: flags for review
rather than auto-activating discovered tools.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.knowledge_entry import KnowledgeEntry
from app.models.plugin import Plugin

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tool discovery patterns
# ---------------------------------------------------------------------------

# Keywords that suggest a tool/API/library is being discussed
TOOL_INDICATORS = [
    "new api", "api release", "sdk", "library", "framework",
    "command-line", "cli tool", "open source", "new tool",
    "released", "launched", "announced", "version",
    "python package", "npm package", "gem", "crate",
]

# Known tool categories mapped from keywords
CATEGORY_MAP: dict[str, str] = {
    "llm": "llm",
    "language model": "llm",
    "gpt": "llm",
    "claude": "llm",
    "openai": "llm",
    "anthropic": "llm",
    "api": "api",
    "sdk": "sdk",
    "database": "database",
    "vector": "database",
    "embedding": "embedding",
    "browser": "browser",
    "automation": "automation",
    "testing": "testing",
    "devops": "devops",
    "deploy": "devops",
    "monitoring": "monitoring",
    "security": "security",
    "search": "search",
    "rag": "rag",
    "agent": "agent",
    "workflow": "workflow",
}


class ToolDiscovery:
    """Scans knowledge entries to discover new tools Jarvis could use.

    Uses pattern matching (configurable) and LLM analysis to identify
    tool announcements. Discovered tools are flagged for review —
    they are NOT auto-activated.
    """

    def __init__(self) -> None:
        self._discovery_keywords = TOOL_INDICATORS

    async def scan_entries(
        self,
        hours_back: int = 168,
        min_confidence: str = "low",
    ) -> dict[str, Any]:
        """Scan recent knowledge entries for tool discoveries.

        Args:
            hours_back: How many hours of history to scan
            min_confidence: Minimum confidence level (high, medium, low)

        Returns:
            Scan results with discovered tools
        """
        from datetime import timedelta

        since = datetime.now(UTC) - timedelta(hours=hours_back)
        start_time = time.time()

        async with async_session_factory() as db:
            result = await db.execute(
                select(KnowledgeEntry)
                .where(
                    and_(
                        KnowledgeEntry.created_at >= since,
                        KnowledgeEntry.is_read.is_(False),
                    )
                )
                .order_by(KnowledgeEntry.created_at.desc())
                .limit(100)
            )
            entries = result.scalars().all()

        discovered: list[dict[str, Any]] = []
        for entry in entries:
            tool = await self._analyze_entry(entry)
            if tool:
                confidence = tool.get("confidence", "low")
                confidence_order = {"high": 0, "medium": 1, "low": 2}
                min_order = confidence_order.get(min_confidence, 2)
                if confidence_order.get(confidence, 2) <= min_order:
                    discovered.append(tool)

        elapsed = time.time() - start_time

        return {
            "entries_scanned": len(entries),
            "tools_found": discovered,
            "scan_time_seconds": round(elapsed, 2),
        }

    async def _analyze_entry(
        self, entry: KnowledgeEntry
    ) -> dict[str, Any] | None:
        """Analyze a single entry for tool discovery signals.

        Uses pattern matching first, then falls back to LLM analysis
        for high-confidence signals.
        """
        text_to_analyze = " ".join(
            filter(
                None,
                [entry.title, entry.summary, entry.content],
            )
        ).lower()

        if not text_to_analyze:
            return None

        # Step 1: Pattern matching
        matched_keywords = [
            kw for kw in self._discovery_keywords if kw in text_to_analyze
        ]

        if not matched_keywords:
            return None

        # Determine confidence based on match quality
        title_lower = entry.title.lower()
        title_match = any(kw in title_lower for kw in matched_keywords)
        has_url = bool(entry.url)
        keyword_count = len(matched_keywords)

        if title_match and has_url and keyword_count >= 2:
            confidence = "high"
        elif title_match or (has_url and keyword_count >= 2):
            confidence = "medium"
        else:
            confidence = "low"

        # Determine category
        category = self._categorize_tool(text_to_analyze)

        # Build description
        description_parts: list[str] = []
        if entry.summary:
            description_parts.append(entry.summary[:300])
        if matched_keywords:
            description_parts.append(
                f"Keywords: {', '.join(matched_keywords)}"
            )
        description = " | ".join(description_parts)

        return {
            "entry_id": str(entry.id),
            "title": entry.title,
            "url": entry.url,
            "description": description,
            "category": category,
            "confidence": confidence,
        }

    def _extract_tool_name(self, title: str) -> str | None:
        """Extract a likely tool name from the title."""
        # Try to extract the first noun phrase from the title
        # (simple heuristic: remove common prefixes)
        prefixes = [
            "Introducing", "Announcing", "New", "Launching",
            "Release of", "Version", "Meet",
        ]
        for prefix in prefixes:
            if title.startswith(prefix):
                rest = title[len(prefix):].strip()
                # Take up to the first colon or period
                for sep in [":", ".", " - ", " — "]:
                    if sep in rest:
                        return rest.split(sep)[0].strip()
                return rest.split(",")[0].strip()

        # Fallback: take the first meaningful segment
        for sep in [":", ".", " - ", " — "]:
            if sep in title:
                return title.split(sep)[0].strip()

        return title[:80].strip()

    def _categorize_tool(self, text: str) -> str | None:
        """Categorize a tool based on keywords in the text."""
        for keyword, category in CATEGORY_MAP.items():
            if keyword in text:
                return category
        return None

    async def flag_for_review(
        self, discovered_tool: dict[str, Any]
    ) -> dict[str, Any]:
        """Flag a discovered tool in the plugin registry for review.

        This does NOT auto-activate the tool — it creates a pending
        plugin entry that requires human approval.
        """
        async with async_session_factory() as db:
            # Check if a plugin with this name already exists
            existing = await db.execute(
                select(Plugin).where(Plugin.name == discovered_tool.get("title", "")[:100])
            )
            if existing.scalar_one_or_none():
                return {"status": "skipped", "reason": "Already registered"}

            # Create a plugin entry in pending state
            plugin = Plugin(
                id=uuid.uuid4(),
                name=discovered_tool.get("title", "Unknown Tool")[:100],
                version="0.1.0",
                description=discovered_tool.get("description", "")[:500],
                author="tool-discovery",
                enabled=False,  # Requires manual approval
                config={
                    "discovered_at": datetime.now(UTC).isoformat(),
                    "source_url": discovered_tool.get("url"),
                    "category": discovered_tool.get("category"),
                    "confidence": discovered_tool.get("confidence", "low"),
                    "status": "pending_review",
                },
            )
            db.add(plugin)
            await db.commit()

            logger.info(
                "Tool flagged for review",
                name=plugin.name,
                confidence=discovered_tool.get("confidence"),
            )

            return {"status": "flagged", "plugin_id": str(plugin.id)}

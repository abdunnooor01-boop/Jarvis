"""FeedCrawler service — fetches and parses content from curated knowledge sources.

Supports multiple source types:
- Hacker News (Firebase API)
- GitHub Trending (HTML scraping)
- RSS/Atom feeds (feedparser)
- API changelogs (JSON API endpoints)
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.knowledge_entry import FeedSource, KnowledgeEntry

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default curated sources
# ---------------------------------------------------------------------------

DEFAULT_SOURCES: list[dict[str, Any]] = [
    {
        "name": "Hacker News Top Stories",
        "source_type": "hackernews",
        "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "config": {"max_items": 30, "item_url_template": "https://hacker-news.firebaseio.com/v0/item/{}.json"},
        "fetch_interval_minutes": 60,
    },
    {
        "name": "GitHub Trending AI/ML",
        "source_type": "github_trending",
        "url": "https://github.com/trending?since=weekly&spoken_language_code=",
        "config": {"language": "python", "since": "weekly", "max_repos": 20},
        "fetch_interval_minutes": 180,
    },
    {
        "name": "OpenAI Changelog",
        "source_type": "changelog",
        "url": "https://api.openai.com/v1/",
        "config": {"provider": "openai", "feed_url": "https://openai.com/blog/changelog/rss.xml"},
        "fetch_interval_minutes": 360,
    },
    {
        "name": "Anthropic Updates",
        "source_type": "changelog",
        "url": "https://docs.anthropic.com/en/docs",
        "config": {"provider": "anthropic", "feed_url": "https://docs.anthropic.com/en/docs/rss.xml"},
        "fetch_interval_minutes": 360,
    },
    {
        "name": "The Verge - AI/Tech",
        "source_type": "rss",
        "url": "https://www.theverge.com/ai-artificial-intelligence/rss.xml",
        "config": {"max_items": 10},
        "fetch_interval_minutes": 120,
    },
    {
        "name": "Ars Technica - AI",
        "source_type": "rss",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "config": {"max_items": 10},
        "fetch_interval_minutes": 120,
    },
    {
        "name": "TechCrunch - AI",
        "source_type": "rss",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "config": {"max_items": 10},
        "fetch_interval_minutes": 120,
    },
]


# ---------------------------------------------------------------------------
# Rate limiter helper
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple per-source rate limiter using in-memory timestamps."""

    def __init__(self) -> None:
        self._last_fetch: dict[str, float] = {}

    def can_fetch(self, source_name: str, min_interval_seconds: float = 30.0) -> bool:
        """Check if enough time has passed since the last fetch."""
        last = self._last_fetch.get(source_name)
        if last is None:
            return True
        return (datetime.now(UTC).timestamp() - last) >= min_interval_seconds

    def record_fetch(self, source_name: str) -> None:
        """Record that a fetch occurred."""
        self._last_fetch[source_name] = datetime.now(UTC).timestamp()


# ---------------------------------------------------------------------------
# FeedCrawler
# ---------------------------------------------------------------------------


class FeedCrawler:
    """Fetches and parses content from curated knowledge sources.

    Each source type gets its own parser method. The service is designed
    to be imported and used by the API layer or a background scheduler.
    """

    def __init__(self) -> None:
        self._http_client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Jarvis-Knowledge-Crawler/1.0",
                    "Accept": "text/html,application/xml,application/json,*/*",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ------------------------------------------------------------------
    # Source seeding
    # ------------------------------------------------------------------

    async def ensure_default_sources(self) -> list[FeedSource]:
        """Seed default sources into the database if they don't exist."""
        async with async_session_factory() as db:
            existing = await db.execute(
                select(FeedSource.name).where(FeedSource.is_active)
            )
            existing_names = {row[0] for row in existing.fetchall()}

            sources: list[FeedSource] = []
            for src_data in DEFAULT_SOURCES:
                if src_data["name"] in existing_names:
                    continue
                source = FeedSource(
                    id=uuid.uuid4(),
                    name=src_data["name"],
                    source_type=src_data["source_type"],
                    url=src_data["url"],
                    config=src_data.get("config"),
                    fetch_interval_minutes=src_data.get("fetch_interval_minutes", 60),
                    is_active=True,
                )
                db.add(source)
                sources.append(source)

            if sources:
                await db.commit()
                logger.info("Seeded default feed sources", count=len(sources))
                for s in sources:
                    await db.refresh(s)

            return sources

    # ------------------------------------------------------------------
    # Main crawl methods
    # ------------------------------------------------------------------

    async def crawl_source(self, source_id: str) -> dict[str, Any]:
        """Crawl a single source by its ID.

        Returns a dict with results/error info.
        """
        async with async_session_factory() as db:
            result = await db.execute(
                select(FeedSource).where(FeedSource.id == uuid.UUID(str(source_id)))
            )
            source = result.scalar_one_or_none()

            if source is None:
                return {"source_id": source_id, "error": "Source not found", "entries": []}

            if not source.is_active:
                return {"source_id": source_id, "error": "Source is inactive", "entries": []}

            entries: list[KnowledgeEntry] = []
            error: str | None = None

            try:
                if source.source_type == "hackernews":
                    entries = await self._fetch_hackernews(source)
                elif source.source_type == "github_trending":
                    entries = await self._fetch_github_trending(source)
                elif source.source_type == "rss":
                    entries = await self._fetch_rss(source)
                elif source.source_type == "changelog":
                    entries = await self._fetch_changelog(source)
                else:
                    error = f"Unknown source type: {source.source_type}"

                # Update source status
                source.last_fetched_at = datetime.now(UTC)
                if error:
                    source.last_error = error
                    source.consecutive_failures = (source.consecutive_failures or 0) + 1
                else:
                    source.last_error = None
                    source.consecutive_failures = 0
                await db.commit()

            except Exception as e:
                error = str(e)
                source.last_error = error
                source.consecutive_failures = (source.consecutive_failures or 0) + 1
                await db.commit()
                logger.error(
                    "Failed to crawl source",
                    source_id=source_id,
                    source_name=source.name,
                    error=error,
                )

            # Store entries
            stored_count = 0
            if entries:
                stored_count = await self._store_entries(entries, source)

            return {
                "source_id": str(source.id),
                "source_name": source.name,
                "entries_found": len(entries),
                "entries_stored": stored_count,
                "error": error,
            }

    async def crawl_all(self) -> list[dict[str, Any]]:
        """Crawl all active sources and return results."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(FeedSource).where(
                    FeedSource.is_active,
                    FeedSource.consecutive_failures < 5,  # Skip repeatedly failing sources
                )
            )
            sources = result.scalars().all()

        results: list[dict[str, Any]] = []
        for source in sources:
            # Rate limiting between sources
            if not self._rate_limiter.can_fetch(source.name, 5.0):
                logger.info("Rate limited, skipping source", source=source.name)
                continue

            result = await self.crawl_source(str(source.id))
            results.append(result)
            self._rate_limiter.record_fetch(source.name)

            # Small delay between sources to be polite
            await asyncio.sleep(1)

        return results

    # ------------------------------------------------------------------
    # Source-specific fetchers
    # ------------------------------------------------------------------

    async def _fetch_hackernews(self, source: FeedSource) -> list[KnowledgeEntry]:
        """Fetch top stories from Hacker News Firebase API."""
        client = await self._get_client()
        config = source.config or {}
        max_items = config.get("max_items", 30)
        item_url_template = config.get("item_url_template", "https://hacker-news.firebaseio.com/v0/item/{}.json")

        # Get top story IDs
        resp = await client.get(source.url)
        resp.raise_for_status()
        story_ids = resp.json()[:max_items]

        # Fetch item details concurrently
        tasks = [client.get(item_url_template.format(sid)) for sid in story_ids]
        item_responses = await asyncio.gather(*tasks, return_exceptions=True)

        entries: list[KnowledgeEntry] = []
        for item_resp in item_responses:
            if isinstance(item_resp, Exception):
                continue
            if item_resp.status_code != 200:
                continue
            item = item_resp.json()
            if not item or item.get("type") != "story":
                continue

            title = item.get("title", "")
            if not title:
                continue

            entry = KnowledgeEntry(
                id=uuid.uuid4(),
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=item.get("url"),
                summary=item.get("text", "")[:500] if item.get("text") else None,
                author=item.get("by"),
                published_at=datetime.fromtimestamp(
                    item.get("time", 0), tz=UTC
                ) if item.get("time") else None,
                topics=["hackernews", "tech"],
                metadata_={
                    "score": item.get("score", 0),
                    "descendants": item.get("descendants", 0),
                    "hn_id": item.get("id"),
                },
            )
            entries.append(entry)

        return entries

    async def _fetch_github_trending(self, source: FeedSource) -> list[KnowledgeEntry]:
        """Fetch trending repositories from GitHub Trending page."""
        client = await self._get_client()
        config = source.config or {}
        max_repos = config.get("max_repos", 20)

        # Fetch the trending page
        url = "https://github.com/trending"
        since = config.get("since", "weekly")
        if since:
            url += f"?since={since}"

        resp = await client.get(url, headers={"Accept": "text/html"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.Box-row")[:max_repos]

        entries: list[KnowledgeEntry] = []
        for article in articles:
            h2 = article.select_one("h2")
            if not h2:
                continue

            # Extract repo name
            repo_link = h2.select_one("a")
            if not repo_link:
                continue
            repo_name = repo_link.get_text(strip=True).replace(" ", "")

            # Extract description
            desc_elem = article.select_one("p")
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract language
            lang_elem = article.select_one("[itemprop='programmingLanguage']")
            language = lang_elem.get_text(strip=True) if lang_elem else None

            # Extract stars
            stars_elem = article.select_one("a[href*='/stargazers']")
            stars = None
            if stars_elem:
                stars_text = stars_elem.get_text(strip=True).replace(",", "")
                with contextlib.suppress(ValueError):
                    stars = int(stars_text)

            repo_url = f"https://github.com/{repo_name}"

            # Only keep AI/ML related repos
            topics_list = ["github", "trending"]
            if language:
                topics_list.append(language.lower())

            # Check if it's AI/ML related
            is_ai_ml = False
            ai_keywords = ["ai", "ml", "machine-learning", "deep-learning", "llm", "gpt",
                          "neural", "transformer", "language-model", "pytorch", "tensorflow",
                          "rag", "agent", "embedding", "vector", "chatbot", "openai",
                          "anthropic", "claude", "langchain"]
            repo_lower = repo_name.lower()
            if any(kw in repo_lower for kw in ai_keywords):
                is_ai_ml = True
            if description and any(kw in description.lower() for kw in ai_keywords):
                is_ai_ml = True

            if not is_ai_ml:
                continue

            entry = KnowledgeEntry(
                id=uuid.uuid4(),
                source_id=source.id,
                source_name=source.name,
                title=f"GitHub: {repo_name}",
                url=repo_url,
                summary=description,
                topics=topics_list,
                metadata_={
                    "language": language,
                    "stars": stars,
                    "repo": repo_name,
                },
            )
            entries.append(entry)

        return entries

    async def _fetch_rss(self, source: FeedSource) -> list[KnowledgeEntry]:
        """Fetch and parse an RSS/Atom feed."""
        client = await self._get_client()
        config = source.config or {}
        max_items = config.get("max_items", 10)

        resp = await client.get(source.url)
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)

        entries: list[KnowledgeEntry] = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            if not title:
                continue

            # Parse published date
            published = None
            if entry.get("published_parsed"):
                try:
                    from time import mktime
                    published = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=UTC
                    )
                except Exception:
                    pass

            # Extract summary/content
            summary = entry.get("summary", "")
            content = None
            if entry.get("content"):
                content = entry.content[0].get("value", "")[:5000] if entry.content else None

            # Extract author
            author = None
            if entry.get("author"):
                author = entry.author

            # Extract topics from tags
            topics = ["rss", source.name.lower().replace(" ", "-")]
            if entry.get("tags"):
                for tag in entry.tags:
                    term = tag.get("term", "")
                    if term:
                        topics.append(term.lower().replace(" ", "-"))

            knowledge_entry = KnowledgeEntry(
                id=uuid.uuid4(),
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=entry.get("link"),
                summary=summary[:1000] if summary else None,
                content=content,
                author=author,
                published_at=published,
                topics=list(set(topics))[:20],
                metadata_={"source_feed": source.url},
            )
            entries.append(knowledge_entry)

        return entries

    async def _fetch_changelog(self, source: FeedSource) -> list[KnowledgeEntry]:
        """Fetch API changelogs.

        First tries RSS feed if configured, falls back to direct API check.
        """
        config = source.config or {}
        feed_url = config.get("feed_url")
        provider = config.get("provider", "unknown")

        if feed_url:
            # Try RSS-based changelog
            return await self._fetch_rss(
                FeedSource(
                    id=source.id,
                    name=source.name,
                    source_type="rss",
                    url=feed_url,
                    config={"max_items": 10},
                    is_active=True,
                    fetch_interval_minutes=360,
                )
            )

        # Fallback: direct API version check
        client = await self._get_client()
        try:
            resp = await client.get(source.url, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                data = resp.json()
                # Generic check — look for version info
                version = data.get("version") or data.get("api_version") or "unknown"
                entry = KnowledgeEntry(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    source_name=source.name,
                    title=f"{provider.capitalize()} API available",
                    url=source.url,
                    summary=f"{provider.capitalize()} API is responding. Version: {version}",
                    topics=[provider, "api", "changelog"],
                    metadata_={"provider": provider, "version": version},
                )
                return [entry]
        except Exception as e:
            logger.warning(
                "Changelog API check failed",
                provider=provider,
                error=str(e),
            )

        return []

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    async def _store_entries(
        self, entries: list[KnowledgeEntry], source: FeedSource
    ) -> int:
        """Store entries, skipping duplicates by URL hash."""
        stored = 0
        async with async_session_factory() as db:
            for entry in entries:
                # Check for duplicate by URL
                if entry.url:
                    existing = await db.execute(
                        select(KnowledgeEntry).where(
                            KnowledgeEntry.url == entry.url,
                            KnowledgeEntry.source_id == source.id,
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        continue

                db.add(entry)
                stored += 1

            await db.commit()

        return stored

    # ------------------------------------------------------------------
    # Digest generation
    # ------------------------------------------------------------------

    async def generate_digest(
        self,
        hours_back: int = 168,
        max_entries: int = 50,
    ) -> dict[str, Any]:
        """Generate a knowledge digest of recent entries.

        Args:
            hours_back: How many hours of history to include (default 168 = 7 days)
            max_entries: Maximum number of entries in the digest

        Returns:
            A dict with generated_at, total_entries, and entries list
        """
        since = datetime.now(UTC) - timedelta(hours=hours_back)

        async with async_session_factory() as db:
            result = await db.execute(
                select(KnowledgeEntry)
                .where(KnowledgeEntry.created_at >= since)
                .order_by(KnowledgeEntry.created_at.desc())
                .limit(max_entries)
            )
            entries = result.scalars().all()

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_entries": len(entries),
            "entries": [
                {
                    "title": e.title,
                    "url": e.url,
                    "source_name": e.source_name,
                    "summary": e.summary,
                    "topics": e.topics,
                    "published_at": e.published_at.isoformat() if e.published_at else None,
                }
                for e in entries
            ],
        }

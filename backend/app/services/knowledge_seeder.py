"""Knowledge feed seed data — default curated sources for Jarvis's knowledge feeds."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge_feed import KnowledgeSource

logger = get_logger(__name__)

# Default curated sources for Jarvis's knowledge feeds
_DEFAULT_SOURCES = [
    {
        "name": "Hacker News Top Stories",
        "source_type": "api",
        "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "schedule": "hourly",
        "category": "technology",
    },
    {
        "name": "Hacker News New Stories",
        "source_type": "api",
        "url": "https://hacker-news.firebaseio.com/v0/newstories.json",
        "schedule": "hourly",
        "category": "technology",
    },
    {
        "name": "GitHub Trending — AI/ML",
        "source_type": "api",
        "url": "https://api.github.com/search/repositories?q=topic:artificial-intelligence+topic:machine-learning&sort=stars&order=desc&per_page=25",
        "schedule": "daily",
        "category": "ai/ml",
    },
    {
        "name": "GitHub Trending — Python",
        "source_type": "api",
        "url": "https://api.github.com/search/repositories?q=language:python&sort=stars&order=desc&per_page=25",
        "schedule": "daily",
        "category": "python",
    },
    {
        "name": "Python.org Blog (RSS)",
        "source_type": "rss",
        "url": "https://blog.python.org/feeds/posts/default",
        "schedule": "daily",
        "category": "python",
    },
    {
        "name": "Real Python Tutorials (RSS)",
        "source_type": "rss",
        "url": "https://realpython.com/atom.xml",
        "schedule": "daily",
        "category": "python",
    },
    {
        "name": "OpenAI Blog (RSS)",
        "source_type": "rss",
        "url": "https://openai.com/blog/rss.xml",
        "schedule": "daily",
        "category": "ai/ml",
    },
    {
        "name": "Google AI Blog (RSS)",
        "source_type": "rss",
        "url": "https://ai.googleblog.com/feeds/posts/default",
        "schedule": "daily",
        "category": "ai/ml",
    },
    {
        "name": "Meta AI Blog (RSS)",
        "source_type": "rss",
        "url": "https://ai.meta.com/blog/rss.xml",
        "schedule": "daily",
        "category": "ai/ml",
    },
    {
        "name": "Anthropic Blog (RSS)",
        "source_type": "rss",
        "url": "https://anthropic.com/blog/rss.xml",
        "schedule": "daily",
        "category": "ai/ml",
    },
    {
        "name": "Dev.to AI/ML Articles (RSS)",
        "source_type": "rss",
        "url": "https://dev.to/feed/tag/artificial-intelligence",
        "schedule": "daily",
        "category": "ai/ml",
    },
    {
        "name": "ArXiv AI Papers (RSS)",
        "source_type": "rss",
        "url": "http://export.arxiv.org/rss/cs.AI",
        "schedule": "daily",
        "category": "research",
    },
    {
        "name": "ArXiv Machine Learning (RSS)",
        "source_type": "rss",
        "url": "http://export.arxiv.org/rss/cs.LG",
        "schedule": "daily",
        "category": "research",
    },
    {
        "name": "Changelog Podcast (RSS)",
        "source_type": "rss",
        "url": "https://changelog.com/podcast/feed",
        "schedule": "weekly",
        "category": "devtools",
    },
]


async def ensure_knowledge_sources_seeded(db: AsyncSession) -> list[KnowledgeSource]:
    """Seed default knowledge sources if they don't exist yet.

    Returns the list of all active sources.
    """
    result = await db.execute(select(func.count(KnowledgeSource.id)))
    count = result.scalar() or 0
    if count > 0:
        # Already seeded — return active sources
        result = await db.execute(
            select(KnowledgeSource)
            .where(KnowledgeSource.enabled == True)
            .order_by(KnowledgeSource.name)
        )
        return list(result.scalars().all())

    logger.info("Seeding default knowledge sources", count=len(_DEFAULT_SOURCES))
    sources = []
    for src in _DEFAULT_SOURCES:
        source = KnowledgeSource(
            id=uuid.uuid4(),
            name=src["name"],
            source_type=src["source_type"],
            url=src["url"],
            schedule=src["schedule"],
            category=src["category"],
            last_fetch_status="never",
            enabled=True,
        )
        db.add(source)
        sources.append(source)

    await db.commit()
    for s in sources:
        await db.refresh(s)

    logger.info("Knowledge sources seeded successfully", count=len(sources))
    return sources
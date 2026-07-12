"""Jarvis AI Assistant — FastAPI Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth as auth_routes
from app.api import chat as chat_routes
from app.api import dev as dev_routes
from app.api import dev_logs as dev_log_routes
from app.api import freelance as freelance_routes
from app.api import knowledge as knowledge_routes
from app.api import memory as memory_routes
from app.api import plugins as plugin_routes
from app.api import system as system_routes
from app.api import tasks as task_routes
from app.api import vision as vision_routes
from app.api import voice as voice_routes
from app.api.ws import router as ws_routes
from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.security import add_security_headers, validate_and_warn
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:  # noqa: ARG001
    """Application lifespan — startup and shutdown."""
    setup_logging()
    logger = get_logger(__name__)

    # Validate environment on startup
    validate_and_warn()

    # Create database tables on startup (dev mode — switch to Alembic for prod)
    async with engine.begin() as conn:
        # Enable pgvector extension if available
        try:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
        except Exception:
            logger.info("pgvector extension not available (expected with SQLite)")
        await conn.run_sync(Base.metadata.create_all)

    # Log low-power mode
    if settings.low_power_mode:
        logger.warning(
            "LOW-POWER MODE ACTIVE",
            max_memory_mb=settings.max_memory_mb or "unlimited",
            max_concurrent_tasks=min(1, settings.max_concurrent_tasks),
            crawl_interval_hours=48,
            auto_register_tools=False,
            embedding_generation=False,
        )
    else:
        logger.info("Normal power mode", max_concurrent_tasks=settings.max_concurrent_tasks)

    # Preload plugins
    try:
        from app.services.tool_executor import ToolExecutor

        await ToolExecutor.preload_plugins()
    except Exception as preload_err:
        logger.error("Failed to preload plugins during startup", error=str(preload_err))

    logger.info(
        "Starting Jarvis API",
        environment=settings.environment,
        version=settings.app_version,
    )

    # Start the knowledge feed pipeline orchestrator
    from app.services.scheduler import scheduler as pipeline_scheduler

    pipeline_scheduler.start()
    effective_crawl_interval = (
        48 if settings.low_power_mode else settings.crawl_interval_hours
    )
    logger.info(
        "Pipeline orchestrator started",
        crawl_interval_hours=effective_crawl_interval,
        digest_day=settings.digest_day_of_week,
        mode="low-power" if settings.low_power_mode else "normal",
    )

    yield

    # Shutdown the pipeline orchestrator
    await pipeline_scheduler.stop()
    logger.info("Shutting down Jarvis API")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware (must be first to handle preflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
app.middleware("http")(add_security_headers)

# Register routers
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(dev_routes.router)
app.include_router(dev_log_routes.router)
app.include_router(freelance_routes.router)
app.include_router(knowledge_routes.router)
app.include_router(memory_routes.router)
app.include_router(system_routes.router)
app.include_router(vision_routes.router)
app.include_router(voice_routes.router)
app.include_router(plugin_routes.router)
app.include_router(task_routes.router)
app.include_router(ws_routes)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler returning RFC 7807 Problem Details."""
    logger = get_logger(__name__)
    logger.error("Unhandled exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred. Please try again later.",
            "instance": str(request.url),
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}

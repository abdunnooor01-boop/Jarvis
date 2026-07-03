"""Jarvis AI Assistant — FastAPI Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth as auth_routes
from app.api import chat as chat_routes
from app.api import voice as voice_routes
from app.api import plugins as plugin_routes
from app.api.ws import router as ws_routes
from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:  # noqa: ARG001
    """Application lifespan — startup and shutdown."""
    setup_logging()
    logger = get_logger(__name__)

    # Create database tables on startup (dev mode — switch to Alembic for prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
    yield
    logger.info("Shutting down Jarvis API")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(voice_routes.router)
app.include_router(plugin_routes.router)
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
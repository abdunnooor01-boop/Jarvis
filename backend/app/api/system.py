"""System health and performance API endpoints.

Provides:
- /api/v1/system/health — comprehensive system health with memory/CPU/mode
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from app.config import settings
from app.core.logging import get_logger
from app.services.scheduler import scheduler

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


def _get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return round(memory_info.rss / (1024 * 1024), 1)
    except ImportError:
        # Fallback: read from /proc/self/status
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return float(line.split()[1]) / 1024
        except (FileNotFoundError, IndexError, ValueError):
            pass
        return 0.0


def _get_cpu_percent() -> float:
    """Get current CPU usage percentage."""
    try:
        import psutil

        return psutil.Process(os.getpid()).cpu_percent(interval=0.1)
    except ImportError:
        return 0.0


def _format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.1f} GB"
    if bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} MB"
    if bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val} B"


@router.get("/health")
async def system_health() -> dict:
    """Comprehensive system health endpoint.

    Reports current resource usage, operational mode,
    and background pipeline status.
    """
    memory_mb = _get_memory_usage_mb()
    cpu_percent = _get_cpu_percent()
    scheduler_status = scheduler.get_status()

    return {
        "status": "healthy",
        "version": settings.app_version,
        "mode": "low-power" if settings.low_power_mode else "normal",
        "resources": {
            "memory_usage_mb": memory_mb,
            "memory_limit_mb": settings.max_memory_mb or None,
            "cpu_percent": cpu_percent,
            "max_concurrent_tasks": settings.max_concurrent_tasks,
        },
        "scheduler": scheduler_status,
        "low_power_settings": {
            "enabled": settings.low_power_mode,
            "crawl_interval_hours": (
                48 if settings.low_power_mode else settings.crawl_interval_hours
            ),
            "auto_register_tools": not settings.low_power_mode,
            "digest_frequency": "weekly" if settings.low_power_mode else "daily",
            "embedding_generation": not settings.low_power_mode,
            "concurrent_background_tasks": (
                1 if settings.low_power_mode else settings.max_concurrent_tasks
            ),
        },
    }

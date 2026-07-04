"""Plugin API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.plugin import Plugin
from app.models.user import User
from app.schemas.plugin import PluginDetail, PluginInstall, PluginResponse, PluginToggle
from app.services.plugin_loader import PluginLoader

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


@router.get("", response_model=list[PluginResponse])
async def list_plugins(
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> list[PluginResponse]:
    """List all installed and auto-discovered plugins."""
    loader = PluginLoader()
    discovered_dirs = loader.discover_plugins()
    discovered_manifests = []

    for p_dir in discovered_dirs:
        manifest = loader.load_manifest(p_dir)
        if manifest:
            discovered_manifests.append(manifest)

    # Sync with DB first to ensure consistent DB entries
    await loader.sync_plugins_with_db(discovered_manifests)

    # Query DB to get current enabled status and IDs
    result = await db.execute(select(Plugin))
    db_plugins = {p.name: p for p in result.scalars().all()}

    response = []
    for manifest in discovered_manifests:
        db_plugin = db_plugins.get(manifest.name)
        if db_plugin:
            response.append(
                PluginResponse(
                    id=db_plugin.id,
                    name=db_plugin.name,
                    version=db_plugin.version,
                    description=db_plugin.description,
                    author=db_plugin.author,
                    enabled=db_plugin.enabled,
                    installed_at=db_plugin.installed_at,
                )
            )

    return response


@router.get("/{name}", response_model=PluginDetail)
async def get_plugin_details(
    name: str,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> PluginDetail:
    """Get details of a specific plugin by name."""
    loader = PluginLoader()
    discovered_dirs = loader.discover_plugins()

    target_manifest = None
    for p_dir in discovered_dirs:
        manifest = loader.load_manifest(p_dir)
        if manifest and manifest.name == name:
            target_manifest = manifest
            break

    if not target_manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{name}' not found on disk.",
        )

    result = await db.execute(select(Plugin).where(Plugin.name == name))
    db_plugin = result.scalar_one_or_none()

    if not db_plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{name}' not registered in database.",
        )

    return PluginDetail(
        id=db_plugin.id,
        name=db_plugin.name,
        version=db_plugin.version,
        description=db_plugin.description,
        author=db_plugin.author,
        enabled=db_plugin.enabled,
        installed_at=db_plugin.installed_at,
        tools=target_manifest.tools,
        settings=db_plugin.settings,
    )


@router.post("/{name}/toggle", response_model=PluginResponse)
async def toggle_plugin(
    name: str,
    payload: PluginToggle,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> PluginResponse:
    """Enable or disable a plugin."""
    result = await db.execute(select(Plugin).where(Plugin.name == name))
    db_plugin = result.scalar_one_or_none()

    if not db_plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{name}' not found.",
        )

    db_plugin.enabled = payload.enabled
    await db.flush()

    return PluginResponse(
        id=db_plugin.id,
        name=db_plugin.name,
        version=db_plugin.version,
        description=db_plugin.description,
        author=db_plugin.author,
        enabled=db_plugin.enabled,
        installed_at=db_plugin.installed_at,
    )


@router.post("/install", response_model=dict[str, str])
async def install_plugin(
    payload: PluginInstall,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
) -> dict[str, str]:
    """Scaffolding/placeholder endpoint for installing a plugin."""
    # This is a scaffolding placeholder that simulates a successful plugin installation.
    return {
        "status": "success",
        "message": f"Plugin from '{payload.path}' is successfully registered/queued for installation.",
    }

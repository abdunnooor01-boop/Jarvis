"""Tools API — tool registry introspection + approval allowlist management.

Phase 15 desktop control: the frontend needs to know which tools exist and
whether they require owner approval, and the owner manages their "remember
my choice" allowlist here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.tool_allowlist import ToolAllowlistEntry
from app.models.user import User
from app.services.tool_executor import ToolExecutor
from app.services.tool_policy import ToolPolicyService, tool_requires_approval

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


class ToolInfoResponse(BaseModel):
    """A registered tool with its approval policy."""

    name: str
    description: str
    parameters: dict[str, Any]
    approval_required: bool
    # Whether the tool's approval depends on its `action` argument
    action_sensitive: bool = False


class ToolListResponse(BaseModel):
    tools: list[ToolInfoResponse]


class AllowlistEntryCreate(BaseModel):
    """Create an allowlist entry (remember an approval)."""

    tool_name: str = Field(..., min_length=1, max_length=64)
    # Optional partial argument pattern — None or {} means "any arguments".
    arguments: dict[str, Any] | None = None


class AllowlistEntryResponse(BaseModel):
    id: str
    tool_name: str
    arguments: dict[str, Any] | None
    created_at: str


class AllowlistResponse(BaseModel):
    entries: list[AllowlistEntryResponse]


def _build_tool_info(definition: dict[str, Any]) -> ToolInfoResponse:
    """Convert an OpenAI tool definition to ToolInfoResponse."""
    fn = definition.get("function", {})
    name = fn.get("name", "")
    action_sensitive = name in {"file_ops", "clipboard"}
    # For action-sensitive tools, report the worst case (a write needs
    # approval) so the UI surfaces the tool as gated.
    approval = tool_requires_approval(
        name, {"action": "write"} if action_sensitive else None
    )
    return ToolInfoResponse(
        name=name,
        description=fn.get("description", ""),
        parameters=fn.get("parameters", {}),
        approval_required=approval,
        action_sensitive=action_sensitive,
    )


@router.get("", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """List all registered tools and whether each needs owner approval."""
    executor = ToolExecutor()
    definitions = executor.get_tool_definitions()
    tools = [
        _build_tool_info(defn)
        for defn in sorted(definitions, key=lambda d: d["function"]["name"])
    ]
    return ToolListResponse(tools=tools)


@router.get("/allowlist", response_model=AllowlistResponse)
async def list_allowlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AllowlistResponse:
    """List the current user's remembered tool approvals."""
    service = ToolPolicyService(db)
    entries = await service.list_allowlist(str(current_user.id))
    return AllowlistResponse(
        entries=[
            AllowlistEntryResponse(
                id=e.id,
                tool_name=e.tool_name,
                arguments=e.arguments,
                created_at=e.created_at.isoformat() if e.created_at else "",
            )
            for e in entries
        ]
    )


@router.post(
    "/allowlist",
    response_model=AllowlistEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_allowlist_entry(
    body: AllowlistEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AllowlistEntryResponse:
    """Remember an approval for a tool call (None arguments = any call)."""
    service = ToolPolicyService(db)
    entry = await service.add_allowlist_entry(
        user_id=str(current_user.id),
        tool_name=body.tool_name,
        arguments=body.arguments,
    )
    return AllowlistEntryResponse(
        id=entry.id,
        tool_name=entry.tool_name,
        arguments=entry.arguments,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


@router.delete("/allowlist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_allowlist_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a remembered tool approval."""
    service = ToolPolicyService(db)
    removed = await service.remove_allowlist_entry(str(current_user.id), entry_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allowlist entry not found",
        )


# Re-export for the ws layer to reuse the policy classification
__all__ = ["router", "ToolAllowlistEntry", "ToolPolicyService", "tool_requires_approval"]

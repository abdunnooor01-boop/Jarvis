"""Tool allowlist ORM model — per-user remembered tool approvals.

When the owner approves a desktop-control tool call with "remember this
choice", an entry is created here so the same tool call is auto-approved
in the future (the allowlist is the backend half of the approval-gated
computer-control flow).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ToolAllowlistEntry(Base):
    """A single allowlist entry: a tool call the owner pre-approved."""

    __tablename__ = "tool_allowlist"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    # None = any arguments for this tool are allowed; otherwise the entry
    # matches only when every key in `arguments` equals the call's argument.
    arguments: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ToolAllowlistEntry(id={self.id}, tool={self.tool_name!r}, "
            f"args={self.arguments!r})>"
        )

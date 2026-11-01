"""Pending-action schemas (spec #69, #85).

These describe a write an agent proposed and a human still has to approve. Only
the approval endpoints accept them; MCP never sees this model directly.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PendingStatus = Literal["pending", "confirmed", "rejected", "failed", "expired"]


class PendingActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    record_type: str
    summary: str
    payload: dict[str, Any]
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    token_name: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    resolved_at: datetime | None = None


class PendingActionList(BaseModel):
    items: list[PendingActionRead]
    total: int
    page: int
    page_size: int
    # Number of rows still awaiting a decision, across all pages.
    pending_total: int = 0


class PendingActionConfirm(BaseModel):
    # Set when the user has seen a duplicate warning and wants the record anyway
    # (spec #41), matching ``?force=true`` on the normal create endpoints.
    force: bool = Field(default=False)

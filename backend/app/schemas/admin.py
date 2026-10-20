"""Admin-only API models (spec #5, #58, #78)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AdminUserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None
    display_name: str | None
    role: str
    status: str
    records: int
    trips: int
    created_at: datetime


class AdminUserList(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    role: Literal["USER", "ADMIN"] | None = None
    status: Literal["ACTIVE", "DISABLED"] | None = None


class AdminSystemRead(BaseModel):
    version: str
    users: int
    active_users: int
    admins: int
    records: int
    trips: int
    audit_logs: int


class AdminAuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    meta: dict[str, Any] | None
    created_at: datetime


class AdminAuditLogList(BaseModel):
    items: list[AdminAuditLogRead]
    total: int
    page: int
    page_size: int

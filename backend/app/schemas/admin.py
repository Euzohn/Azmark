"""Admin-only API models (spec #5, #58, #78)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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


class AdminUserCreate(BaseModel):
    """Admin-created account (spec #60): initial password is conveyed to the
    new user out-of-band; they should change it on first login."""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=100)
    role: Literal["USER", "ADMIN"] = "USER"


class AdminUserList(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    role: Literal["USER", "ADMIN"] | None = None
    status: Literal["ACTIVE", "DISABLED"] | None = None
    new_password: str | None = Field(default=None, min_length=6, max_length=128)


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
    ip: str | None
    ip_hash: str | None
    user_agent: str | None
    request_id: str | None
    created_at: datetime


class AdminAuditLogList(BaseModel):
    items: list[AdminAuditLogRead]
    total: int
    page: int
    page_size: int

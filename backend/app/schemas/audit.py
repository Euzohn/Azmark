import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    resource_type: str | None
    resource_id: str | None
    meta: dict[str, Any] | None
    # Tracing context (spec #47). ip_hash is a salted hash — never a raw IP;
    # request_id groups the rows one request produced.
    ip_hash: str | None
    user_agent: str | None
    request_id: str | None
    created_at: datetime


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int

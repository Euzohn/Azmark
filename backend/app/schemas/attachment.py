import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentRead(BaseModel):
    """Public attachment metadata (never exposes ``storage_key``)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    filename: str
    mime_type: str
    size: int
    created_at: datetime


class AttachmentList(BaseModel):
    items: list[AttachmentRead]
    total: int

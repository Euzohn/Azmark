import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PhotoUpdate(BaseModel):
    """Editable metadata. Upload itself is multipart; EXIF fills these in."""

    filename: str | None = Field(default=None, min_length=1, max_length=255)
    captured_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    trip_id: uuid.UUID | None = None


class PhotoRead(BaseModel):
    """Public photo metadata (never exposes ``storage_key``)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    mime_type: str
    size: int
    captured_at: datetime | None
    latitude: float | None
    longitude: float | None
    trip_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PhotoList(BaseModel):
    items: list[PhotoRead]
    total: int
    page: int
    page_size: int

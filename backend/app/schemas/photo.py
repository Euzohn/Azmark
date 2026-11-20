import uuid
from datetime import date, datetime

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


class PhotoTripCandidate(BaseModel):
    """A trip a photo could belong to, with the deterministic match reasons."""

    trip_id: uuid.UUID
    trip_name: str
    start_date: date | None
    end_date: date | None
    #: "time" (captured within the trip dates) and/or "geo" (GPS near an anchor).
    reasons: list[str]
    distance_km: float | None
    confidence: str


class PhotoSuggestion(BaseModel):
    photo: PhotoRead
    candidates: list[PhotoTripCandidate]


class PhotoSuggestions(BaseModel):
    items: list[PhotoSuggestion]
    #: All unfiled photos, including ones with no EXIF time or GPS.
    unassigned_total: int


class PhotoAssignment(BaseModel):
    photo_id: uuid.UUID
    trip_id: uuid.UUID


class PhotoOrganizeInput(BaseModel):
    assignments: list[PhotoAssignment] = Field(min_length=1, max_length=200)


class PhotoOrganizeResult(BaseModel):
    updated: int

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Place type vocabulary (spec #14). The DB column stays permissive String(20).
PlaceType = Literal[
    "airport",
    "train_station",
    "bus_station",
    "port",
    "hotel",
    "restaurant",
    "attraction",
    "city",
    "place",
    "other",
]

PLACE_TYPES: tuple[str, ...] = (
    "airport",
    "train_station",
    "bus_station",
    "port",
    "hotel",
    "restaurant",
    "attraction",
    "city",
    "place",
    "other",
)


class PlaceBase(BaseModel):
    type: PlaceType = "place"
    country: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    localized_name: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    external_ids: dict[str, Any] | None = None


class PlaceCreate(PlaceBase):
    pass


class PlaceUpdate(BaseModel):
    type: PlaceType | None = None
    country: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    localized_name: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    external_ids: dict[str, Any] | None = None


class PlaceRead(PlaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PlaceSummary(BaseModel):
    """Compact place attached to an Activity card (docs §4.4)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    localized_name: str | None = None
    city: str | None = None


class PlaceList(BaseModel):
    items: list[PlaceRead]
    total: int
    page: int
    page_size: int

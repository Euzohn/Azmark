import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timezones import normalize_timezone
from app.schemas.place import PlaceSummary

# Activity type vocabulary (spec #18 lists the field but no values). The DB
# column stays a permissive String(40) for future/imported values.
ActivityType = Literal[
    "sightseeing",
    "dining",
    "shopping",
    "culture",
    "outdoor",
    "event",
    "visit",
    "other",
]

ACTIVITY_TYPES: tuple[str, ...] = (
    "sightseeing",
    "dining",
    "shopping",
    "culture",
    "outdoor",
    "event",
    "visit",
    "other",
)


def _upper_currency(value: str | None) -> str | None:
    return value.strip().upper() if isinstance(value, str) else value


class ActivityBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: ActivityType = "other"
    place_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = None
    trip_id: uuid.UUID | None = None

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return _upper_currency(value)

    @field_validator("timezone", mode="before")
    @classmethod
    def _normalize_timezone(cls, value: object) -> object:
        return normalize_timezone(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_window(self) -> "ActivityBase":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("end_at must not be before start_at")
        return self


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: ActivityType | None = None
    place_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = None
    trip_id: uuid.UUID | None = None

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return _upper_currency(value)

    @field_validator("timezone", mode="before")
    @classmethod
    def _normalize_timezone(cls, value: object) -> object:
        return normalize_timezone(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_window(self) -> "ActivityUpdate":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("end_at must not be before start_at")
        return self


class ActivityRead(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    # Read-only summary; not accepted on create/update.
    place: PlaceSummary | None = None


class ActivityList(BaseModel):
    items: list[ActivityRead]
    total: int
    page: int
    page_size: int

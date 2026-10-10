import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.transport import FlightRead


class _TripDates(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> "_TripDates":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class TripBase(_TripDates):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    status: str = Field(default="planned", max_length=20)


class TripCreate(TripBase):
    pass


class TripUpdate(_TripDates):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, max_length=20)


class TripRead(TripBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TripDetail(TripRead):
    """Trip plus every transport record grouped under it (flights + trains)."""

    records: list[FlightRead] = []


class TripList(BaseModel):
    items: list[TripRead]
    total: int
    page: int
    page_size: int

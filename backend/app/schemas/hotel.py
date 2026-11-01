import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _HotelDates(BaseModel):
    @model_validator(mode="after")
    def _check_dates(self) -> "_HotelDates":
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValueError("check_out must not be before check_in")
        return self


class HotelBase(_HotelDates):
    hotel: str = Field(min_length=1, max_length=160)
    check_in: date
    check_out: date | None = None
    room_type: str | None = Field(default=None, max_length=60)
    room_number: str | None = Field(default=None, max_length=20)
    booking_reference: str | None = Field(default=None, max_length=64)
    price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None
    trip_id: uuid.UUID | None = None
    status: str = Field(default="scheduled", max_length=20)


class HotelCreate(HotelBase):
    pass


class HotelUpdate(BaseModel):
    hotel: str | None = Field(default=None, min_length=1, max_length=160)
    check_in: date | None = None
    check_out: date | None = None
    room_type: str | None = Field(default=None, max_length=60)
    room_number: str | None = Field(default=None, max_length=20)
    booking_reference: str | None = Field(default=None, max_length=64)
    price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None
    trip_id: uuid.UUID | None = None
    status: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _check_dates(self) -> "HotelUpdate":
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValueError("check_out must not be before check_in")
        return self


class HotelRead(HotelBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class HotelList(BaseModel):
    items: list[HotelRead]
    total: int
    page: int
    page_size: int

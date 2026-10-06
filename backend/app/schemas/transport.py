import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FlightBase(BaseModel):
    status: str = Field(default="scheduled", max_length=20)
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    departure_timezone: str | None = Field(default=None, max_length=64)
    arrival_timezone: str | None = Field(default=None, max_length=64)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    carrier: str | None = Field(default=None, max_length=120)
    service_number: str | None = Field(default=None, max_length=40)
    seat: str | None = Field(default=None, max_length=10)
    terminal: str | None = Field(default=None, max_length=20)
    gate: str | None = Field(default=None, max_length=20)
    booking_reference: str | None = Field(default=None, max_length=64)
    ticket_number: str | None = Field(default=None, max_length=64)
    price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    notes: str | None = None


class FlightCreate(FlightBase):
    pass


class FlightUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    departure_timezone: str | None = Field(default=None, max_length=64)
    arrival_timezone: str | None = Field(default=None, max_length=64)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    carrier: str | None = Field(default=None, max_length=120)
    service_number: str | None = Field(default=None, max_length=40)
    seat: str | None = Field(default=None, max_length=10)
    terminal: str | None = Field(default=None, max_length=20)
    gate: str | None = Field(default=None, max_length=20)
    booking_reference: str | None = Field(default=None, max_length=64)
    ticket_number: str | None = Field(default=None, max_length=64)
    price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    notes: str | None = None


class FlightRead(FlightBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    trip_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class FlightList(BaseModel):
    items: list[FlightRead]
    total: int
    page: int
    page_size: int

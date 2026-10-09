import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FlightBase(BaseModel):
    status: str = Field(default="scheduled", max_length=20)
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    actual_departure_time: datetime | None = None
    actual_arrival_time: datetime | None = None
    departure_timezone: str | None = Field(default=None, max_length=64)
    arrival_timezone: str | None = Field(default=None, max_length=64)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    carrier: str | None = Field(default=None, max_length=120)
    airline_code: str | None = Field(default=None, max_length=3)
    service_number: str | None = Field(default=None, max_length=40)
    seat: str | None = Field(default=None, max_length=10)
    departure_terminal: str | None = Field(default=None, max_length=20)
    departure_gate: str | None = Field(default=None, max_length=20)
    arrival_terminal: str | None = Field(default=None, max_length=20)
    arrival_gate: str | None = Field(default=None, max_length=20)
    check_in_desk: str | None = Field(default=None, max_length=20)
    baggage_belt: str | None = Field(default=None, max_length=20)
    aircraft_model: str | None = Field(default=None, max_length=60)
    aircraft_reg: str | None = Field(default=None, max_length=20)
    booking_reference: str | None = Field(default=None, max_length=64)
    ticket_number: str | None = Field(default=None, max_length=64)
    purchase_credential_type: str | None = Field(default=None, max_length=20)
    purchase_credential: str | None = Field(default=None, max_length=64)
    price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    distance: Decimal | None = None
    notes: str | None = None
    trip_id: uuid.UUID | None = None


class FlightCreate(FlightBase):
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)


class FlightUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    actual_departure_time: datetime | None = None
    actual_arrival_time: datetime | None = None
    departure_timezone: str | None = Field(default=None, max_length=64)
    arrival_timezone: str | None = Field(default=None, max_length=64)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    carrier: str | None = Field(default=None, max_length=120)
    airline_code: str | None = Field(default=None, max_length=3)
    service_number: str | None = Field(default=None, max_length=40)
    seat: str | None = Field(default=None, max_length=10)
    departure_terminal: str | None = Field(default=None, max_length=20)
    departure_gate: str | None = Field(default=None, max_length=20)
    arrival_terminal: str | None = Field(default=None, max_length=20)
    arrival_gate: str | None = Field(default=None, max_length=20)
    check_in_desk: str | None = Field(default=None, max_length=20)
    baggage_belt: str | None = Field(default=None, max_length=20)
    aircraft_model: str | None = Field(default=None, max_length=60)
    aircraft_reg: str | None = Field(default=None, max_length=20)
    booking_reference: str | None = Field(default=None, max_length=64)
    ticket_number: str | None = Field(default=None, max_length=64)
    purchase_credential_type: str | None = Field(default=None, max_length=20)
    purchase_credential: str | None = Field(default=None, max_length=64)
    price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    distance: Decimal | None = None
    notes: str | None = None
    trip_id: uuid.UUID | None = None


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

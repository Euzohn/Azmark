from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field


class FlightLookupRequest(BaseModel):
    flight_number: str = Field(min_length=2, max_length=10)
    date: DateType | None = None
    provider: str | None = Field(default=None, max_length=40)


class FlightLookupResponse(BaseModel):
    flight_number: str
    airline_code: str | None = None
    airline_name: str | None = None
    airline_name_zh: str | None = None
    origin_iata: str | None = None
    destination_iata: str | None = None
    origin_name: str | None = None
    destination_name: str | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    actual_departure_time: datetime | None = None
    actual_arrival_time: datetime | None = None
    departure_terminal: str | None = None
    departure_gate: str | None = None
    arrival_terminal: str | None = None
    arrival_gate: str | None = None
    check_in_desk: str | None = None
    baggage_belt: str | None = None
    aircraft_model: str | None = None
    aircraft_reg: str | None = None
    departure_timezone: str | None = None
    arrival_timezone: str | None = None
    aircraft: str | None = None
    status: str | None = None
    distance: float | None = None
    source: str | None = None

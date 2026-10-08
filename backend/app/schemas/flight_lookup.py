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
    origin_iata: str | None = None
    destination_iata: str | None = None
    origin_name: str | None = None
    destination_name: str | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    aircraft: str | None = None
    status: str | None = None
    source: str | None = None

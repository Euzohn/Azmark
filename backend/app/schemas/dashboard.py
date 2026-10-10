"""Response models for dashboard, statistics, timeline and map (spec #10, #28)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.transport import FlightRead


class DashboardStats(BaseModel):
    countries: int
    cities: int
    journeys: int
    distance_km: float
    flights: int
    trains: int
    trips: int


class DashboardRead(BaseModel):
    stats: DashboardStats
    recent: list[FlightRead]
    upcoming: FlightRead | None


class BreakdownItem(BaseModel):
    label: str
    name: str | None = None
    count: int


class StatisticsRead(BaseModel):
    by_month: list[BreakdownItem]
    by_airline: list[BreakdownItem]
    by_alliance: list[BreakdownItem]
    by_airport: list[BreakdownItem]
    by_aircraft: list[BreakdownItem]


class MapPoint(BaseModel):
    code: str | None = None
    name: str | None = None
    name_zh: str | None = None
    city: str | None = None
    city_zh: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None


class MapRoute(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    service_number: str | None = None
    airline_code: str | None = None
    carrier: str | None = None
    departure_time: datetime | None = None
    origin: MapPoint
    destination: MapPoint
    distance_km: float | None = None


class MapRoutesRead(BaseModel):
    items: list[MapRoute]
    total: int

"""Response models for dashboard, statistics, timeline and map (spec #10, #28)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardRecord(BaseModel):
    """Common fields for the dashboard's cross-type recent/upcoming lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    status: str
    origin: str | None = None
    destination: str | None = None
    service_number: str | None = None
    carrier: str | None = None
    airline_code: str | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    trip_id: uuid.UUID | None = None


class DashboardStats(BaseModel):
    countries: int
    cities: int
    journeys: int
    distance_km: float
    flights: int
    trains: int
    transports: int
    trips: int


class DashboardRead(BaseModel):
    stats: DashboardStats
    recent: list[DashboardRecord]
    upcoming: DashboardRecord | None


class BreakdownItem(BaseModel):
    label: str
    name: str | None = None
    count: int


class StatisticsTotals(BaseModel):
    countries: int
    cities: int
    distance_km: float
    trips: int
    flights: int
    trains: int
    transports: int


class StatisticsRead(BaseModel):
    totals: StatisticsTotals
    by_year: list[BreakdownItem]
    by_month: list[BreakdownItem]
    by_day: list[BreakdownItem]
    # Flight
    by_airline: list[BreakdownItem]
    by_alliance: list[BreakdownItem]
    by_airport: list[BreakdownItem]
    by_aircraft: list[BreakdownItem]
    by_cabin: list[BreakdownItem]
    by_seat_type: list[BreakdownItem]
    # Train
    by_train_operator: list[BreakdownItem]
    by_train_type: list[BreakdownItem]
    by_station: list[BreakdownItem]
    by_train_class: list[BreakdownItem]
    by_train_seat_type: list[BreakdownItem]


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

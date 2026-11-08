"""Response models for dashboard, statistics, timeline and map (spec #10, #28)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.expense import ExpenseStatistics, ExpenseSummary


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
    departure_timezone: str | None = None
    arrival_timezone: str | None = None
    trip_id: uuid.UUID | None = None


class DashboardStats(BaseModel):
    countries: int
    cities: int
    journeys: int
    distance_km: float
    flights: int
    trains: int
    transports: int
    hotels: int = 0
    trips: int


class BreakdownItem(BaseModel):
    label: str
    name: str | None = None
    count: int


class DashboardRead(BaseModel):
    stats: DashboardStats
    recent: list[DashboardRecord]
    upcoming: DashboardRecord | None
    # Chronological record counts by month ("YYYY-MM"). The client slices the
    # tail to render a rolling activity trend without a second request.
    by_month: list[BreakdownItem] = []


class StatisticsTotals(BaseModel):
    countries: int
    cities: int
    distance_km: float
    trips: int
    flights: int
    trains: int
    transports: int
    hotels: int = 0


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
    # Spend is reported in the user's currency; unconverted buckets stay separate.
    expense_summary: ExpenseSummary
    # Richer spend aggregates (category / month / trip / currency) for the
    # statistics page. ``expense_summary`` is kept for the compact trip view.
    expense_stats: ExpenseStatistics


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


class MapHotel(BaseModel):
    """A geocoded accommodation stay pinned on the map (spec #10/#17)."""

    id: uuid.UUID
    name: str
    lat: float
    lon: float
    check_in: date
    check_out: date | None = None
    status: str


class MapRoutesRead(BaseModel):
    items: list[MapRoute]
    total: int
    # Stays with coordinates render as pins next to the flight arcs (spec #10).
    hotels: list[MapHotel] = []

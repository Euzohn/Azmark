"""Response model for the annual Travel Wrapped report (spec #87).

Reuses the map/dashboard point vocabulary so the frontend can localise origin
and destination names exactly like the map page does.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.dashboard import BreakdownItem, MapPoint
from app.schemas.expense import ExpenseSummary


class WrappedTotals(BaseModel):
    countries: int
    cities: int
    distance_km: float
    trips: int
    flights: int
    trains: int
    transports: int
    hotels: int
    hotel_nights: int
    activities: int
    travel_days: int


class WrappedRoute(BaseModel):
    """The single longest journey of the year, for the highlight chapter."""

    id: uuid.UUID
    type: str
    service_number: str | None = None
    carrier: str | None = None
    origin: MapPoint
    destination: MapPoint
    distance_km: float
    departure_date: date | None = None


class WrappedRead(BaseModel):
    year: int
    # Years the user actually has data in; lets the page render a selector.
    available_years: list[int]
    totals: WrappedTotals
    # Monthly journey counts, chronological, labelled "YYYY-MM".
    by_month: list[BreakdownItem]
    top_airlines: list[BreakdownItem]
    top_airports: list[BreakdownItem]
    top_stations: list[BreakdownItem]
    top_aircraft: list[BreakdownItem]
    # label carries the English city name, name the Chinese one (when known);
    # the frontend picks per locale.
    most_visited_city: BreakdownItem | None = None
    # label is the trip name; count is how many of the year's journeys sit in it.
    favorite_trip: BreakdownItem | None = None
    longest_route: WrappedRoute | None = None
    first_journey: date | None = None
    last_journey: date | None = None
    # Spend recorded in that year, normalised to the user's report currency.
    spend: ExpenseSummary

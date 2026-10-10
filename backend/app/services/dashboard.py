"""User-scoped aggregates for dashboard, statistics, timeline and map.

See spec #10 (Dashboard), #28 (Statistics), #26 (Timeline), #27 (Map).
All queries are scoped by user_id — callers must never bypass it (spec #57).
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.repositories.transport import TransportRepository
from app.schemas.dashboard import (
    BreakdownItem,
    DashboardRead,
    DashboardStats,
    MapPoint,
    MapRoute,
    MapRoutesRead,
    StatisticsRead,
)
from app.services import reference
from app.utils.geo import haversine_km


def _naive_utc(dt: datetime) -> datetime:
    """Normalise to naive UTC for DB-agnostic comparison (SQLite ↔ Postgres)."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.records = TransportRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _distance_km(record: TransportRecord) -> float | None:
        """Return the record's distance, falling back to haversine from coords."""
        if record.distance is not None:
            return float(record.distance)
        origin = reference.get_airport_by_iata(record.origin or "")
        dest = reference.get_airport_by_iata(record.destination or "")
        if not origin or not dest:
            return None
        olat, olon = origin.get("lat"), origin.get("lon")
        dlat, dlon = dest.get("lat"), dest.get("lon")
        if None in (olat, olon, dlat, dlon):
            return None
        return round(haversine_km(olat, olon, dlat, dlon), 1)

    @staticmethod
    def _map_point(code: str | None) -> MapPoint:
        airport = reference.get_airport_by_iata(code or "")
        if not airport:
            return MapPoint(code=code)
        return MapPoint(
            code=airport["iata"],
            name=airport.get("name"),
            name_zh=airport.get("name_zh"),
            city=airport.get("city"),
            city_zh=airport.get("city_zh"),
            country=airport.get("country"),
            lat=airport.get("lat"),
            lon=airport.get("lon"),
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def overview(self, *, user_id: uuid.UUID) -> DashboardRead:
        all_records = self.records.list_all(user_id=user_id)
        flights_desc = [r for r in all_records if r.type == "flight"]
        trains = [r for r in all_records if r.type == "train"]

        countries: set[str] = set()
        cities: set[str] = set()
        distance = 0.0
        for record in all_records:
            for code in (record.origin, record.destination):
                airport = reference.get_airport_by_iata(code or "")
                if not airport:
                    continue
                if airport.get("country"):
                    countries.add(airport["country"])
                if airport.get("city"):
                    cities.add(airport["city"])
            km = self._distance_km(record)
            if km:
                distance += km

        trips_total = (
            self.db.scalar(select(func.count()).select_from(Trip).where(Trip.user_id == user_id))
            or 0
        )

        now_naive = datetime.now(UTC).replace(tzinfo=None)
        upcoming: TransportRecord | None = None
        for record in reversed(flights_desc):
            if record.departure_time and _naive_utc(record.departure_time) > now_naive:
                upcoming = record
                break

        return DashboardRead(
            stats=DashboardStats(
                countries=len(countries),
                cities=len(cities),
                journeys=len(all_records),
                distance_km=round(distance, 1),
                flights=len(flights_desc),
                trains=len(trains),
                trips=int(trips_total),
            ),
            recent=flights_desc[:5],
            upcoming=upcoming,
        )

    def statistics(self, *, user_id: uuid.UUID) -> StatisticsRead:
        all_records = self.records.list_all(user_id=user_id)
        flights = [r for r in all_records if r.type == "flight"]

        months: Counter[str] = Counter()
        airlines: Counter[str] = Counter()
        alliances: Counter[str] = Counter()
        airports: Counter[str] = Counter()
        aircraft: Counter[str] = Counter()

        for record in flights:
            if record.departure_time:
                months[_naive_utc(record.departure_time).strftime("%Y-%m")] += 1
            key = record.airline_code or record.carrier
            if key:
                airlines[key] += 1
                if record.airline_code:
                    airline = reference.get_airline_by_iata(record.airline_code)
                    alliance = airline.get("alliance") if airline else None
                    if alliance:
                        alliances[alliance] += 1
            for code in (record.origin, record.destination):
                if code:
                    airports[code] += 1
            if record.aircraft_model:
                aircraft[record.aircraft_model] += 1

        by_airline = [
            BreakdownItem(
                label=code,
                name=(
                    reference.get_airline_by_iata(code).get("name")
                    if reference.get_airline_by_iata(code)
                    else None
                ),
                count=count,
            )
            for code, count in airlines.most_common()
        ]

        by_airport = [
            BreakdownItem(
                label=code,
                name=(
                    reference.get_airport_by_iata(code).get("name")
                    if reference.get_airport_by_iata(code)
                    else None
                ),
                count=count,
            )
            for code, count in airports.most_common()
        ]

        return StatisticsRead(
            by_month=sorted(
                (BreakdownItem(label=m, count=c) for m, c in months.items()),
                key=lambda item: item.label,
            ),
            by_airline=by_airline,
            by_alliance=[
                BreakdownItem(label=code, count=count) for code, count in alliances.most_common()
            ],
            by_airport=by_airport,
            by_aircraft=[
                BreakdownItem(label=model, count=count) for model, count in aircraft.most_common()
            ],
        )

    def timeline(self, *, user_id: uuid.UUID) -> list[TransportRecord]:
        return self.records.list_all(user_id=user_id)

    def routes(self, *, user_id: uuid.UUID) -> MapRoutesRead:
        all_records = self.records.list_all(user_id=user_id)
        items = [
            MapRoute(
                id=record.id,
                type=record.type,
                status=record.status,
                service_number=record.service_number,
                airline_code=record.airline_code,
                carrier=record.carrier,
                departure_time=record.departure_time,
                origin=self._map_point(record.origin),
                destination=self._map_point(record.destination),
                distance_km=self._distance_km(record),
            )
            for record in all_records
            if record.type == "flight"
        ]
        return MapRoutesRead(items=items, total=len(items))

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
    StatisticsTotals,
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
        other = [r for r in all_records if r.type == "other"]

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
                transports=len(other),
                trips=int(trips_total),
            ),
            recent=flights_desc[:5],
            upcoming=upcoming,
        )

    def statistics(self, *, user_id: uuid.UUID) -> StatisticsRead:
        all_records = self.records.list_all(user_id=user_id)
        flights = [r for r in all_records if r.type == "flight"]
        trains = [r for r in all_records if r.type == "train"]
        other = [r for r in all_records if r.type == "other"]

        years: Counter[str] = Counter()
        months: Counter[str] = Counter()
        days: Counter[str] = Counter()
        airlines: Counter[str] = Counter()
        alliances: Counter[str] = Counter()
        airports: Counter[str] = Counter()
        aircraft: Counter[str] = Counter()
        cabins: Counter[str] = Counter()
        seat_types: Counter[str] = Counter()
        train_operators: Counter[str] = Counter()
        train_types: Counter[str] = Counter()
        stations: Counter[str] = Counter()
        train_classes: Counter[str] = Counter()
        train_seat_types: Counter[str] = Counter()

        countries: set[str] = set()
        cities: set[str] = set()
        distance = 0.0

        for record in all_records:
            if record.departure_time:
                departure = _naive_utc(record.departure_time)
                years[departure.strftime("%Y")] += 1
                months[departure.strftime("%Y-%m")] += 1
                days[departure.strftime("%Y-%m-%d")] += 1

            for place in (record.origin, record.destination):
                if not place:
                    continue
                airport = reference.get_airport_by_iata(place)
                if airport:
                    if airport.get("country"):
                        countries.add(airport["country"])
                    if airport.get("city"):
                        cities.add(airport["city"])
                elif record.type in {"train", "other"}:
                    # Stations/docks are free text; count distinct endpoints as
                    # places so train-only journals still get a city total.
                    cities.add(place.strip())

            km = self._distance_km(record)
            if km:
                distance += km

            if record.type == "flight":
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
                if record.cabin_class:
                    cabins[record.cabin_class] += 1
                if record.seat_type:
                    seat_types[record.seat_type] += 1
            elif record.type == "train":
                if record.carrier:
                    train_operators[record.carrier] += 1
                if record.train_type:
                    train_types[record.train_type] += 1
                for station in (record.origin, record.destination):
                    if station:
                        stations[station] += 1
                if record.cabin_class:
                    train_classes[record.cabin_class] += 1
                if record.seat_type:
                    train_seat_types[record.seat_type] += 1

        by_airline = []
        for code, count in airlines.most_common():
            airline = reference.get_airline_by_iata(code)
            by_airline.append(
                BreakdownItem(
                    label=code,
                    name=airline.get("name") if airline else None,
                    count=count,
                )
            )

        by_airport = []
        for code, count in airports.most_common():
            airport = reference.get_airport_by_iata(code)
            by_airport.append(
                BreakdownItem(
                    label=code,
                    name=airport.get("name") if airport else None,
                    count=count,
                )
            )

        trips_total = (
            self.db.scalar(select(func.count()).select_from(Trip).where(Trip.user_id == user_id))
            or 0
        )

        return StatisticsRead(
            totals=StatisticsTotals(
                countries=len(countries),
                cities=len(cities),
                distance_km=round(distance, 1),
                trips=int(trips_total),
                flights=len(flights),
                trains=len(trains),
                transports=len(other),
            ),
            by_year=self._chronological(years),
            by_month=self._chronological(months),
            by_day=self._chronological(days),
            by_airline=by_airline,
            by_alliance=self._ranked(alliances),
            by_airport=by_airport,
            by_aircraft=self._ranked(aircraft),
            by_cabin=self._ranked(cabins),
            by_seat_type=self._ranked(seat_types),
            by_train_operator=self._ranked(train_operators),
            by_train_type=self._ranked(train_types),
            by_station=self._ranked(stations),
            by_train_class=self._ranked(train_classes),
            by_train_seat_type=self._ranked(train_seat_types),
        )

    @staticmethod
    def _ranked(counter: Counter[str]) -> list[BreakdownItem]:
        return [BreakdownItem(label=label, count=count) for label, count in counter.most_common()]

    @staticmethod
    def _chronological(counter: Counter[str]) -> list[BreakdownItem]:
        return [BreakdownItem(label=label, count=count) for label, count in sorted(counter.items())]

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

"""User-scoped aggregates for dashboard, statistics, timeline and map.

See spec #10 (Dashboard), #28 (Statistics), #26 (Timeline), #27 (Map).
All queries are scoped by user_id — callers must never bypass it (spec #57).
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezones import in_timezone
from app.models.activity import Activity
from app.models.hotel import Hotel
from app.models.place import Place
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.user import User
from app.repositories.expense import ExpenseRepository
from app.repositories.transport import TransportRepository
from app.schemas.dashboard import (
    BreakdownItem,
    DashboardRead,
    DashboardStats,
    MapHotel,
    MapPlace,
    MapPoint,
    MapRoute,
    MapRoutesRead,
    StatisticsRead,
    StatisticsTotals,
)
from app.schemas.wrapped import WrappedRead, WrappedRoute, WrappedTotals
from app.services import reference
from app.services.expense import build_expense_statistics, summarize_expenses
from app.utils.geo import haversine_km

# Sentinel year for records without a departure time: they never match any real
# year, so the annual report simply skips them (spec #87).
_EPOCH = date(1, 1, 1)


def _naive_utc(dt: datetime) -> datetime:
    """Normalise to naive UTC for DB-agnostic comparison (SQLite ↔ Postgres)."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.records = TransportRepository(db)
        self.expenses = ExpenseRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _endpoint_distance_km(
        record_type: str, origin: str | None, destination: str | None
    ) -> float | None:
        """Haversine between a record's endpoints (spec #27).

        Flights resolve their endpoints as IATA airports; trains and other
        transport resolve as stations. Only used when the user did not enter a
        ``distance`` (a stored value always wins).
        """
        if record_type == "flight":
            origin_airport = reference.get_airport_by_iata(origin or "")
            dest_airport = reference.get_airport_by_iata(destination or "")
            coords = [
                (origin_airport or {}).get("lat"),
                (origin_airport or {}).get("lon"),
                (dest_airport or {}).get("lat"),
                (dest_airport or {}).get("lon"),
            ]
        else:
            origin_station = reference.station_point(origin or "")
            dest_station = reference.station_point(destination or "")
            if not origin_station or not dest_station:
                return None
            coords = [
                origin_station["lat"],
                origin_station["lon"],
                dest_station["lat"],
                dest_station["lon"],
            ]
        if None in coords:
            return None
        return round(haversine_km(coords[0], coords[1], coords[2], coords[3]), 1)

    @classmethod
    def _distance_km(cls, record: TransportRecord) -> float | None:
        """Return the record's distance, falling back to haversine from coords."""
        if record.distance is not None:
            return float(record.distance)
        return cls._endpoint_distance_km(record.type, record.origin, record.destination)

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

    @staticmethod
    def _station_point(name: str | None) -> MapPoint | None:
        """Resolve a station name for schematic train lines (spec #27).

        Coordinates come from the optional stations registry or the city-level
        fallback in `reference.station_point` (see `AGENTS.md`). A station that
        cannot be resolved is not drawn, instead of being pinned at (0, 0).
        """
        resolved = reference.station_point(name or "")
        if resolved is None:
            return None
        return MapPoint(
            code=name,
            name=name,
            city=resolved.get("city"),
            lat=resolved["lat"],
            lon=resolved["lon"],
        )

    @staticmethod
    def _collect_places(rows: Iterable[Any]) -> tuple[set[str], set[str]]:
        """Return ``(countries, cities)`` seen across *rows*.

        Single source of truth shared by :meth:`overview` and
        :meth:`statistics` so the dashboard and the statistics page can never
        disagree on the city/country totals (spec #10, #28). Accepts either ORM
        records or lightweight ``(type, origin, destination)`` rows.

        Known stations and bilingual airport city names share a city identity.
        Unknown free-text places remain distinct; never guess by stripping a
        direction suffix (e.g. a station may belong to a different municipality).
        """
        countries: set[str] = set()
        cities: set[str] = set()
        for row in rows:
            for place in (row.origin, row.destination):
                if not place:
                    continue
                airport = reference.get_airport_by_iata(place)
                if airport:
                    if airport.get("country"):
                        countries.add(airport["country"])
                    if airport.get("city"):
                        cities.add(reference.airport_city_key(airport))
                elif row.type in {"train", "other"}:
                    cities.add(reference.place_city_key(place))
        return countries, cities

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def _type_counts(self, *, user_id: uuid.UUID) -> dict[str, int]:
        """Count records per transport type in a single GROUP BY query."""
        rows = self.db.execute(
            select(TransportRecord.type, func.count())
            .where(TransportRecord.user_id == user_id)
            .group_by(TransportRecord.type)
        ).all()
        return {record_type: int(count) for record_type, count in rows}

    def _group_counts(
        self,
        *,
        user_id: uuid.UUID,
        column: Any,
        record_type: str | None = None,
    ) -> list[tuple[str, int]]:
        """GROUP BY one column, excluding NULL and empty values.

        Ordered by count desc then value asc — the deterministic counterpart of
        ``Counter.most_common()`` (its tie order is unspecified) that renders
        the same on SQLite and PostgreSQL. Callers who need a stable input for
        further reference lookups can rely on this order.
        """
        conditions = [
            TransportRecord.user_id == user_id,
            column.isnot(None),
            column != "",
        ]
        if record_type is not None:
            conditions.append(TransportRecord.type == record_type)
        stmt = (
            select(column.label("label"), func.count().label("total"))
            .where(*conditions)
            .group_by(column)
            .order_by(func.count().desc(), column.asc())
        )
        return [(str(label), int(total)) for label, total in self.db.execute(stmt).all()]

    def _endpoint_counts(self, *, user_id: uuid.UUID, record_type: str) -> list[tuple[str, int]]:
        """Count endpoint occurrences (origin + destination) for one record type.

        The previous Python pass incremented both ends of every record; the
        UNION ALL of two GROUP BYs keeps that exact semantics in SQL.
        """
        conditions = [
            TransportRecord.user_id == user_id,
            TransportRecord.type == record_type,
        ]

        def part(column: Any):
            return (
                select(column.label("label"), func.count().label("total"))
                .where(*conditions, column.isnot(None), column != "")
                .group_by(column)
            )

        union = part(TransportRecord.origin).union_all(part(TransportRecord.destination)).subquery()
        total = func.sum(union.c.total)
        stmt = (
            select(union.c.label, total)
            .group_by(union.c.label)
            .order_by(total.desc(), union.c.label.asc())
        )
        return [(str(label), int(count)) for label, count in self.db.execute(stmt).all()]

    def _airline_counts(self, *, user_id: uuid.UUID) -> list[tuple[str, int]]:
        """Count flights per airline key (``airline_code or carrier``)."""
        key = func.coalesce(func.nullif(TransportRecord.airline_code, ""), TransportRecord.carrier)
        stmt = (
            select(key.label("label"), func.count().label("total"))
            .where(
                TransportRecord.user_id == user_id,
                TransportRecord.type == "flight",
                key.isnot(None),
                key != "",
            )
            .group_by(key)
            .order_by(func.count().desc(), key.asc())
        )
        return [(str(label), int(total)) for label, total in self.db.execute(stmt).all()]

    def _distance_total(self, *, user_id: uuid.UUID) -> float:
        """Total distance: SUM() user-entered values in SQL, haversine only for
        the (usually few) rows without one, where endpoints resolve from the
        reference data in Python."""
        stored = self.db.scalar(
            select(func.sum(TransportRecord.distance)).where(
                TransportRecord.user_id == user_id,
                TransportRecord.distance.isnot(None),
            )
        )
        distance = float(stored or 0.0)
        rows = self.db.execute(
            select(TransportRecord.type, TransportRecord.origin, TransportRecord.destination)
            .where(
                TransportRecord.user_id == user_id,
                TransportRecord.distance.is_(None),
            )
            .order_by(TransportRecord.id)
        ).all()
        for record_type, origin, destination in rows:
            km = self._endpoint_distance_km(record_type, origin, destination)
            if km:
                distance += km
        return distance

    def _lean_places_rows(self, *, user_id: uuid.UUID) -> list[Any]:
        """Only the columns the city/country tally needs — no ORM hydration."""
        return self.db.execute(
            select(TransportRecord.type, TransportRecord.origin, TransportRecord.destination).where(
                TransportRecord.user_id == user_id
            )
        ).all()

    @staticmethod
    def _items(rows: list[tuple[str, int]]) -> list[BreakdownItem]:
        return [BreakdownItem(label=label, count=count) for label, count in rows]

    def _count_hotels(self, *, user_id: uuid.UUID) -> int:
        """Accommodation is its own table, so it needs its own count (spec #17)."""
        return int(
            self.db.scalar(select(func.count()).select_from(Hotel).where(Hotel.user_id == user_id))
            or 0
        )

    def overview(self, *, user_id: uuid.UUID) -> DashboardRead:
        type_counts = self._type_counts(user_id=user_id)

        months: Counter[str] = Counter()
        for departure_time, timezone in self.db.execute(
            select(TransportRecord.departure_time, TransportRecord.departure_timezone).where(
                TransportRecord.user_id == user_id,
                TransportRecord.departure_time.isnot(None),
            )
        ).all():
            months[in_timezone(departure_time, timezone).strftime("%Y-%m")] += 1

        countries, cities = self._collect_places(self._lean_places_rows(user_id=user_id))

        trips_total = (
            self.db.scalar(select(func.count()).select_from(Trip).where(Trip.user_id == user_id))
            or 0
        )

        now_naive = datetime.now(UTC).replace(tzinfo=None)
        upcoming_candidates = [
            (departure_time, record_id)
            for record_id, departure_time in self.db.execute(
                select(TransportRecord.id, TransportRecord.departure_time)
                .where(
                    TransportRecord.user_id == user_id,
                    TransportRecord.status == "scheduled",
                    TransportRecord.departure_time.isnot(None),
                )
                .order_by(TransportRecord.departure_time.asc(), TransportRecord.id.asc())
            ).all()
            if _naive_utc(departure_time) > now_naive
        ]
        upcoming: TransportRecord | None = None
        if upcoming_candidates:
            _, upcoming_id = min(
                upcoming_candidates, key=lambda candidate: _naive_utc(candidate[0])
            )
            upcoming = self.db.scalar(
                select(TransportRecord).where(
                    TransportRecord.id == upcoming_id,
                    TransportRecord.user_id == user_id,
                )
            )

        return DashboardRead(
            stats=DashboardStats(
                countries=len(countries),
                cities=len(cities),
                journeys=sum(type_counts.values()),
                distance_km=round(self._distance_total(user_id=user_id), 1),
                flights=type_counts.get("flight", 0),
                trains=type_counts.get("train", 0),
                transports=type_counts.get("other", 0),
                hotels=self._count_hotels(user_id=user_id),
                trips=int(trips_total),
            ),
            recent=self.records.list_all(user_id=user_id, limit=5),
            upcoming=upcoming,
            by_month=[
                BreakdownItem(label=label, count=count) for label, count in sorted(months.items())
            ],
        )

    def statistics(self, *, user_id: uuid.UUID) -> StatisticsRead:
        type_counts = self._type_counts(user_id=user_id)

        years: Counter[str] = Counter()
        months: Counter[str] = Counter()
        days: Counter[str] = Counter()
        for departure_time, timezone in self.db.execute(
            select(TransportRecord.departure_time, TransportRecord.departure_timezone).where(
                TransportRecord.user_id == user_id,
                TransportRecord.departure_time.isnot(None),
            )
        ).all():
            departure = in_timezone(departure_time, timezone)
            years[departure.strftime("%Y")] += 1
            months[departure.strftime("%Y-%m")] += 1
            days[departure.strftime("%Y-%m-%d")] += 1

        countries, cities = self._collect_places(self._lean_places_rows(user_id=user_id))

        by_airline: list[BreakdownItem] = []
        for code, count in self._airline_counts(user_id=user_id):
            airline = reference.get_airline_by_iata(code)
            by_airline.append(
                BreakdownItem(
                    label=code,
                    name=airline.get("name") if airline else None,
                    count=count,
                )
            )

        by_airport: list[BreakdownItem] = []
        for code, count in self._endpoint_counts(user_id=user_id, record_type="flight"):
            airport = reference.get_airport_by_iata(code)
            by_airport.append(
                BreakdownItem(
                    label=code,
                    name=airport.get("name") if airport else None,
                    count=count,
                )
            )

        alliances: Counter[str] = Counter()
        for code, count in self._group_counts(
            user_id=user_id, record_type="flight", column=TransportRecord.airline_code
        ):
            airline = reference.get_airline_by_iata(code)
            alliance = airline.get("alliance") if airline else None
            if alliance:
                alliances[alliance] += count

        trips_total = (
            self.db.scalar(select(func.count()).select_from(Trip).where(Trip.user_id == user_id))
            or 0
        )

        user = self.db.get(User, user_id)
        report_currency = (user.currency if user else None) or "CNY"
        expenses = self.expenses.list_for_user(user_id=user_id)
        trip_names = dict(
            self.db.execute(select(Trip.id, Trip.name).where(Trip.user_id == user_id)).all()
        )
        expense_summary = summarize_expenses(expenses, report_currency)
        expense_stats = build_expense_statistics(expenses, report_currency, trip_names=trip_names)

        return StatisticsRead(
            totals=StatisticsTotals(
                countries=len(countries),
                cities=len(cities),
                distance_km=round(self._distance_total(user_id=user_id), 1),
                trips=int(trips_total),
                flights=type_counts.get("flight", 0),
                trains=type_counts.get("train", 0),
                transports=type_counts.get("other", 0),
                hotels=self._count_hotels(user_id=user_id),
            ),
            by_year=self._chronological(years),
            by_month=self._chronological(months),
            by_day=self._chronological(days),
            by_airline=by_airline,
            by_alliance=self._ranked(alliances),
            by_airport=by_airport,
            by_aircraft=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="flight",
                    column=TransportRecord.aircraft_model,
                )
            ),
            by_cabin=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="flight",
                    column=TransportRecord.cabin_class,
                )
            ),
            by_seat_type=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="flight",
                    column=TransportRecord.seat_type,
                )
            ),
            by_train_operator=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="train",
                    column=TransportRecord.carrier,
                )
            ),
            by_train_type=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="train",
                    column=TransportRecord.train_type,
                )
            ),
            by_station=self._items(self._endpoint_counts(user_id=user_id, record_type="train")),
            by_train_class=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="train",
                    column=TransportRecord.cabin_class,
                )
            ),
            by_train_seat_type=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="train",
                    column=TransportRecord.seat_type,
                )
            ),
            expense_summary=expense_summary,
            expense_stats=expense_stats,
        )

    def wrapped(self, *, user_id: uuid.UUID, year: int | None = None) -> WrappedRead:
        """The annual report card (spec #87).

        A journey belongs to the year of its departure **in the departure
        timezone** — a red-eye that lands after midnight still counts for the
        night it started on. Hotels belong to the year of check-in, activities
        to the year of their local start, and expenses to the year of their UTC
        instant, matching the statistics conventions.
        """
        all_records = self.records.list_all(user_id=user_id)

        # Departure day per record, in the departure timezone (see above).
        departure_days: dict[uuid.UUID, date] = {}
        for record in all_records:
            if record.departure_time is not None:
                departure_days[record.id] = in_timezone(
                    record.departure_time, record.departure_timezone
                ).date()

        hotels = list(self.db.scalars(select(Hotel).where(Hotel.user_id == user_id)))
        activities = list(self.db.scalars(select(Activity).where(Activity.user_id == user_id)))
        expenses = self.expenses.list_for_user(user_id=user_id)

        years: set[int] = {day.year for day in departure_days.values()}
        years.update(hotel.check_in.year for hotel in hotels)
        for activity in activities:
            if activity.start_at is not None:
                years.add(in_timezone(activity.start_at, activity.timezone).date().year)
        for expense in expenses:
            if expense.occurred_at is not None:
                years.add(in_timezone(expense.occurred_at, "UTC").date().year)

        target = year if year is not None else (max(years) if years else datetime.now(UTC).year)
        year_records = [r for r in all_records if departure_days.get(r.id, _EPOCH).year == target]

        months: Counter[str] = Counter()
        days: set[date] = set()
        airlines: Counter[str] = Counter()
        airports: Counter[str] = Counter()
        stations: Counter[str] = Counter()
        aircraft: Counter[str] = Counter()
        trip_counts: Counter[uuid.UUID] = Counter()
        city_counts: Counter[str] = Counter()
        # Identity key -> display names; airport cities get a bilingual pair.
        city_display: dict[str, str] = {}
        city_display_zh: dict[str, str] = {}
        distance = 0.0
        longest: tuple[float, TransportRecord] | None = None

        for record in year_records:
            day = departure_days[record.id]
            months[day.strftime("%Y-%m")] += 1
            days.add(day)
            km = self._distance_km(record)
            if km:
                distance += km
                if longest is None or km > longest[0]:
                    longest = (km, record)
            if record.trip_id:
                trip_counts[record.trip_id] += 1
            for place_name in (record.origin, record.destination):
                if not place_name:
                    continue
                airport = reference.get_airport_by_iata(place_name)
                if airport and airport.get("city"):
                    key = reference.airport_city_key(airport)
                    city_counts[key] += 1
                    city_display.setdefault(key, airport["city"])
                    if airport.get("city_zh"):
                        city_display_zh.setdefault(key, airport["city_zh"])
                elif record.type in {"train", "other"}:
                    key = reference.place_city_key(place_name)
                    city_counts[key] += 1
                    city_display.setdefault(key, reference.station_city_label(place_name))
            if record.type == "flight":
                key = record.airline_code or record.carrier
                if key:
                    airlines[key] += 1
                for code in (record.origin, record.destination):
                    if code:
                        airports[code] += 1
                if record.aircraft_model:
                    aircraft[record.aircraft_model] += 1
            else:
                # Trains and other transport share the station leaderboard: both
                # store free-text endpoints.
                for place_name in (record.origin, record.destination):
                    if place_name:
                        stations[place_name] += 1

        countries, cities = self._collect_places(year_records)
        trips = len({r.trip_id for r in year_records if r.trip_id})

        year_hotels = [h for h in hotels if h.check_in.year == target]
        nights = sum((h.check_out - h.check_in).days for h in year_hotels if h.check_out)
        year_activities = sum(
            1
            for activity in activities
            if activity.start_at is not None
            and in_timezone(activity.start_at, activity.timezone).date().year == target
        )
        year_expenses = [
            e
            for e in expenses
            if e.occurred_at is not None and in_timezone(e.occurred_at, "UTC").date().year == target
        ]

        user = self.db.get(User, user_id)
        report_currency = (user.currency if user else None) or "CNY"

        longest_route = None
        if longest is not None:
            km, record = longest
            resolver = self._map_point if record.type == "flight" else self._station_point
            origin = resolver(record.origin) or MapPoint(code=record.origin)
            destination = resolver(record.destination) or MapPoint(code=record.destination)
            longest_route = WrappedRoute(
                id=record.id,
                type=record.type,
                service_number=record.service_number,
                carrier=record.carrier,
                origin=origin,
                destination=destination,
                distance_km=km,
                departure_date=departure_days[record.id],
            )

        favorite_trip = None
        if trip_counts:
            trip_id, count = trip_counts.most_common(1)[0]
            trip = self.db.scalar(select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id))
            if trip is not None:
                favorite_trip = BreakdownItem(label=trip.name, count=count)

        most_visited_city = None
        if city_counts:
            city_key, count = city_counts.most_common(1)[0]
            most_visited_city = BreakdownItem(
                label=city_display[city_key],
                name=city_display_zh.get(city_key),
                count=count,
            )

        return WrappedRead(
            year=target,
            available_years=sorted(years),
            totals=WrappedTotals(
                countries=len(countries),
                cities=len(cities),
                distance_km=round(distance, 1),
                trips=trips,
                flights=sum(1 for r in year_records if r.type == "flight"),
                trains=sum(1 for r in year_records if r.type == "train"),
                transports=sum(1 for r in year_records if r.type == "other"),
                hotels=len(year_hotels),
                hotel_nights=nights,
                activities=year_activities,
                travel_days=len(days),
            ),
            by_month=self._chronological(months),
            top_airlines=self._top_with_airline_names(airlines),
            top_airports=self._top_with_airport_names(airports),
            top_stations=self._ranked(stations)[:5],
            top_aircraft=self._ranked(aircraft)[:5],
            most_visited_city=most_visited_city,
            favorite_trip=favorite_trip,
            longest_route=longest_route,
            first_journey=min(days) if days else None,
            last_journey=max(days) if days else None,
            spend=summarize_expenses(year_expenses, report_currency),
        )

    @staticmethod
    def _top_with_airline_names(counter: Counter[str], *, limit: int = 5) -> list[BreakdownItem]:
        items: list[BreakdownItem] = []
        for code, count in counter.most_common(limit):
            airline = reference.get_airline_by_iata(code)
            items.append(
                BreakdownItem(
                    label=code, name=airline.get("name") if airline else None, count=count
                )
            )
        return items

    @staticmethod
    def _top_with_airport_names(counter: Counter[str], *, limit: int = 5) -> list[BreakdownItem]:
        items: list[BreakdownItem] = []
        for code, count in counter.most_common(limit):
            airport = reference.get_airport_by_iata(code)
            items.append(
                BreakdownItem(
                    label=code, name=airport.get("name") if airport else None, count=count
                )
            )
        return items

    @staticmethod
    def _ranked(counter: Counter[str], *, limit: int | None = None) -> list[BreakdownItem]:
        ranked = [BreakdownItem(label=label, count=count) for label, count in counter.most_common()]
        return ranked if limit is None else ranked[:limit]

    @staticmethod
    def _chronological(counter: Counter[str]) -> list[BreakdownItem]:
        return [BreakdownItem(label=label, count=count) for label, count in sorted(counter.items())]

    def timeline(self, *, user_id: uuid.UUID) -> list[TransportRecord]:
        return self.records.list_all(user_id=user_id)

    def routes(self, *, user_id: uuid.UUID) -> MapRoutesRead:
        all_records = self.records.list_all(user_id=user_id)
        items: list[MapRoute] = []
        for record in all_records:
            if record.type == "flight":
                origin = self._map_point(record.origin)
                destination = self._map_point(record.destination)
            elif record.type in ("train", "other"):
                # Station fields are free text: resolve them through the
                # station registry with the city-level fallback (spec #27).
                # Unresolved endpoints would pin the route at (0, 0), so those
                # records stay off the map until a Place or registry entry
                # provides coordinates.
                origin = self._station_point(record.origin)
                destination = self._station_point(record.destination)
                if origin is None or destination is None:
                    continue
            else:
                continue
            if origin.lat is None or origin.lon is None:
                continue
            if destination.lat is None or destination.lon is None:
                continue
            items.append(
                MapRoute(
                    id=record.id,
                    type=record.type,
                    status=record.status,
                    service_number=record.service_number,
                    airline_code=record.airline_code,
                    carrier=record.carrier,
                    departure_time=record.departure_time,
                    origin=origin,
                    destination=destination,
                    distance_km=self._distance_km(record),
                )
            )
        # Only stays with coordinates can be pinned; the rest stay list-only
        # until the user runs the explicit geocode action (spec #10).
        hotels = [
            MapHotel(
                id=hotel.id,
                name=hotel.hotel,
                lat=hotel.lat,
                lon=hotel.lon,
                check_in=hotel.check_in,
                check_out=hotel.check_out,
                status=hotel.status,
            )
            for hotel in self.db.scalars(
                select(Hotel)
                .where(
                    Hotel.user_id == user_id,
                    Hotel.lat.isnot(None),
                    Hotel.lon.isnot(None),
                )
                .order_by(Hotel.check_in)
            )
        ]
        places = [
            MapPlace(
                id=place.id,
                name=place.name,
                type=place.type,
                lat=place.lat,
                lon=place.lon,
                city=place.city,
            )
            for place in self.db.scalars(
                select(Place)
                .where(
                    Place.user_id == user_id,
                    Place.lat.isnot(None),
                    Place.lon.isnot(None),
                )
                .order_by(Place.name)
            )
        ]
        return MapRoutesRead(items=items, total=len(items), hotels=hotels, places=places)

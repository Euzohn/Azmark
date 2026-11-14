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
from app.models.expense import Expense
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

    # Year-scoped aggregates filter by ``id IN (...)``; SQLite caps a statement
    # at 32766 bound variables (PostgreSQL at 65535), so large years are
    # queried in batches instead of failing on one giant IN list.
    _ID_CHUNK = 5000

    @staticmethod
    def _chunks(ids: list[uuid.UUID]) -> list[list[uuid.UUID]]:
        chunk = DashboardService._ID_CHUNK
        return [ids[start : start + chunk] for start in range(0, len(ids), chunk)]

    @staticmethod
    def _merge_counts(batches: Iterable[Iterable[tuple[Any, int]]]) -> list[tuple[Any, int]]:
        """Combine per-batch GROUP BY results under count DESC, label ASC."""
        totals: Counter[Any] = Counter()
        for batch in batches:
            for label, count in batch:
                totals[label] += count
        return sorted(totals.items(), key=lambda item: (-item[1], item[0]))

    @staticmethod
    def _type_condition(record_type: str | tuple[str, ...]) -> Any:
        if isinstance(record_type, tuple):
            return TransportRecord.type.in_(record_type)
        return TransportRecord.type == record_type

    def _type_counts(
        self, *, user_id: uuid.UUID, record_ids: list[uuid.UUID] | None = None
    ) -> dict[str, int]:
        """Count records per transport type in a single GROUP BY query."""

        def query(ids: list[uuid.UUID] | None) -> dict[str, int]:
            conditions = [TransportRecord.user_id == user_id]
            if ids is not None:
                conditions.append(TransportRecord.id.in_(ids))
            rows = self.db.execute(
                select(TransportRecord.type, func.count())
                .where(*conditions)
                .group_by(TransportRecord.type)
            ).all()
            return {record_type: int(count) for record_type, count in rows}

        if record_ids is None:
            return query(None)
        totals: Counter[str] = Counter()
        for chunk in self._chunks(record_ids):
            totals.update(query(chunk))
        return dict(totals)

    def _group_counts(
        self,
        *,
        user_id: uuid.UUID,
        column: Any,
        record_type: str | tuple[str, ...] | None = None,
        record_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[str, int]]:
        """GROUP BY one column, excluding NULL and empty values.

        Ordered by count desc then value asc — the deterministic counterpart of
        ``Counter.most_common()`` (its tie order is unspecified) that renders
        the same on SQLite and PostgreSQL. Callers who need a stable input for
        further reference lookups can rely on this order.
        """

        def query(ids: list[uuid.UUID] | None) -> list[tuple[str, int]]:
            conditions = [
                TransportRecord.user_id == user_id,
                column.isnot(None),
                column != "",
            ]
            if record_type is not None:
                conditions.append(self._type_condition(record_type))
            if ids is not None:
                conditions.append(TransportRecord.id.in_(ids))
            stmt = (
                select(column.label("label"), func.count().label("total"))
                .where(*conditions)
                .group_by(column)
                .order_by(func.count().desc(), column.asc())
            )
            return [(str(label), int(total)) for label, total in self.db.execute(stmt).all()]

        if record_ids is None:
            return query(None)
        return [
            (str(label), int(total))
            for label, total in self._merge_counts(
                query(chunk) for chunk in self._chunks(record_ids)
            )
        ]

    def _endpoint_counts(
        self,
        *,
        user_id: uuid.UUID,
        record_type: str | tuple[str, ...],
        record_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[str, int]]:
        """Count endpoint occurrences (origin + destination) for record types.

        The previous Python pass incremented both ends of every record; the
        UNION ALL of two GROUP BYs keeps that exact semantics in SQL.

        *record_type* accepts several types because the wrapped report shares
        one station leaderboard between trains and other transport.
        """

        def query(ids: list[uuid.UUID] | None) -> list[tuple[str, int]]:
            conditions = [
                TransportRecord.user_id == user_id,
                self._type_condition(record_type),
            ]
            if ids is not None:
                conditions.append(TransportRecord.id.in_(ids))

            def part(column: Any):
                return (
                    select(column.label("label"), func.count().label("total"))
                    .where(*conditions, column.isnot(None), column != "")
                    .group_by(column)
                )

            union = (
                part(TransportRecord.origin).union_all(part(TransportRecord.destination)).subquery()
            )
            total = func.sum(union.c.total)
            stmt = (
                select(union.c.label, total)
                .group_by(union.c.label)
                .order_by(total.desc(), union.c.label.asc())
            )
            return [(str(label), int(count)) for label, count in self.db.execute(stmt).all()]

        if record_ids is None:
            return query(None)
        return [
            (str(label), int(total))
            for label, total in self._merge_counts(
                query(chunk) for chunk in self._chunks(record_ids)
            )
        ]

    def _airline_counts(
        self, *, user_id: uuid.UUID, record_ids: list[uuid.UUID] | None = None
    ) -> list[tuple[str, int]]:
        """Count flights per airline key (``airline_code or carrier``)."""

        def query(ids: list[uuid.UUID] | None) -> list[tuple[str, int]]:
            key = func.coalesce(
                func.nullif(TransportRecord.airline_code, ""), TransportRecord.carrier
            )
            conditions = [
                TransportRecord.user_id == user_id,
                TransportRecord.type == "flight",
                key.isnot(None),
                key != "",
            ]
            if ids is not None:
                conditions.append(TransportRecord.id.in_(ids))
            stmt = (
                select(key.label("label"), func.count().label("total"))
                .where(*conditions)
                .group_by(key)
                .order_by(func.count().desc(), key.asc())
            )
            return [(str(label), int(total)) for label, total in self.db.execute(stmt).all()]

        if record_ids is None:
            return query(None)
        return [
            (str(label), int(total))
            for label, total in self._merge_counts(
                query(chunk) for chunk in self._chunks(record_ids)
            )
        ]

    def _trip_counts(
        self, *, user_id: uuid.UUID, record_ids: list[uuid.UUID]
    ) -> list[tuple[uuid.UUID, int]]:
        """Records per trip — drives the favorite trip and the trips total."""

        def query(ids: list[uuid.UUID]) -> list[tuple[uuid.UUID, int]]:
            stmt = (
                select(TransportRecord.trip_id.label("label"), func.count().label("total"))
                .where(
                    TransportRecord.user_id == user_id,
                    TransportRecord.trip_id.isnot(None),
                    TransportRecord.id.in_(ids),
                )
                .group_by(TransportRecord.trip_id)
                .order_by(func.count().desc(), TransportRecord.trip_id.asc())
            )
            return [(label, int(total)) for label, total in self.db.execute(stmt).all()]

        return self._merge_counts(query(chunk) for chunk in self._chunks(record_ids))

    def _stored_distance_rows(
        self, *, user_id: uuid.UUID, record_ids: list[uuid.UUID]
    ) -> list[Any]:
        """``(id, distance)`` rows with a user-entered distance."""
        rows: list[Any] = []
        for chunk in self._chunks(record_ids):
            rows.extend(
                self.db.execute(
                    select(TransportRecord.id, TransportRecord.distance).where(
                        TransportRecord.user_id == user_id,
                        TransportRecord.id.in_(chunk),
                        TransportRecord.distance.isnot(None),
                    )
                ).all()
            )
        return rows

    def _null_distance_rows(
        self, *, user_id: uuid.UUID, record_ids: list[uuid.UUID] | None = None
    ) -> list[Any]:
        """``(id, type, origin, destination)`` rows without a stored distance."""

        def query(ids: list[uuid.UUID] | None) -> list[Any]:
            conditions = [
                TransportRecord.user_id == user_id,
                TransportRecord.distance.is_(None),
            ]
            if ids is not None:
                conditions.append(TransportRecord.id.in_(ids))
            return self.db.execute(
                select(
                    TransportRecord.id,
                    TransportRecord.type,
                    TransportRecord.origin,
                    TransportRecord.destination,
                )
                .where(*conditions)
                .order_by(TransportRecord.id)
            ).all()

        if record_ids is None:
            return query(None)
        rows: list[Any] = []
        for chunk in self._chunks(record_ids):
            rows.extend(query(chunk))
        return rows

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
        for row in self._null_distance_rows(user_id=user_id):
            km = self._endpoint_distance_km(row.type, row.origin, row.destination)
            if km:
                distance += km
        return distance

    def _lean_places_rows(
        self, *, user_id: uuid.UUID, record_ids: list[uuid.UUID] | None = None
    ) -> list[Any]:
        """Only the columns the city/country tally needs — no ORM hydration."""

        def query(ids: list[uuid.UUID] | None) -> list[Any]:
            conditions = [TransportRecord.user_id == user_id]
            if ids is not None:
                conditions.append(TransportRecord.id.in_(ids))
            return self.db.execute(
                select(
                    TransportRecord.type,
                    TransportRecord.origin,
                    TransportRecord.destination,
                ).where(*conditions)
            ).all()

        if record_ids is None:
            return query(None)
        rows: list[Any] = []
        for chunk in self._chunks(record_ids):
            rows.extend(query(chunk))
        return rows

    def _expenses_by_ids(
        self, *, user_id: uuid.UUID, expense_ids: list[uuid.UUID]
    ) -> list[Expense]:
        """Hydrate only the expenses of the wrapped year (id refetch)."""
        expenses: list[Expense] = []
        for chunk in self._chunks(expense_ids):
            expenses.extend(
                self.db.scalars(
                    select(Expense).where(
                        Expense.id.in_(chunk),
                        Expense.user_id == user_id,
                    )
                )
            )
        return expenses

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

        Year attribution is the one step SQL cannot express portably (it
        depends on each row's timezone), so it runs over a lean
        ``(id, departure_time, departure_timezone)`` scan. Everything scoped to
        that year then aggregates in SQL — GROUP BY leaderboards, SUM distance,
        a single-row refetch for the longest journey — instead of hydrating the
        user's full record table, mirroring the statistics page (spec #71).
        """
        # Departure day per record, in the departure timezone (see above).
        departure_days: dict[uuid.UUID, date] = {}
        for record_id, departure_time, timezone in self.db.execute(
            select(
                TransportRecord.id,
                TransportRecord.departure_time,
                TransportRecord.departure_timezone,
            ).where(
                TransportRecord.user_id == user_id,
                TransportRecord.departure_time.isnot(None),
            )
        ).all():
            departure_days[record_id] = in_timezone(departure_time, timezone).date()

        hotel_rows = self.db.execute(
            select(Hotel.check_in, Hotel.check_out).where(Hotel.user_id == user_id)
        ).all()
        activity_dates = [
            in_timezone(start_at, timezone).date()
            for start_at, timezone in self.db.execute(
                select(Activity.start_at, Activity.timezone).where(
                    Activity.user_id == user_id,
                    Activity.start_at.isnot(None),
                )
            ).all()
        ]
        expense_dates = {
            expense_id: in_timezone(occurred_at, "UTC").date()
            for expense_id, occurred_at in self.db.execute(
                select(Expense.id, Expense.occurred_at).where(
                    Expense.user_id == user_id,
                    Expense.occurred_at.isnot(None),
                )
            ).all()
        }

        years: set[int] = {day.year for day in departure_days.values()}
        years.update(check_in.year for check_in, _ in hotel_rows)
        years.update(day.year for day in activity_dates)
        years.update(day.year for day in expense_dates.values())

        target = year if year is not None else (max(years) if years else datetime.now(UTC).year)
        year_days = {
            record_id: day for record_id, day in departure_days.items() if day.year == target
        }
        year_ids = list(year_days)

        days: set[date] = set(year_days.values())
        months: Counter[str] = Counter(day.strftime("%Y-%m") for day in year_days.values())

        type_counts = self._type_counts(user_id=user_id, record_ids=year_ids)
        place_rows = self._lean_places_rows(user_id=user_id, record_ids=year_ids)
        countries, cities = self._collect_places(place_rows)
        trip_counts = self._trip_counts(user_id=user_id, record_ids=year_ids)

        city_counts: Counter[str] = Counter()
        # Identity key -> display names; airport cities get a bilingual pair.
        city_display: dict[str, str] = {}
        city_display_zh: dict[str, str] = {}
        for row in place_rows:
            for place_name in (row.origin, row.destination):
                if not place_name:
                    continue
                airport = reference.get_airport_by_iata(place_name)
                if airport and airport.get("city"):
                    key = reference.airport_city_key(airport)
                    city_counts[key] += 1
                    city_display.setdefault(key, airport["city"])
                    if airport.get("city_zh"):
                        city_display_zh.setdefault(key, airport["city_zh"])
                elif row.type in {"train", "other"}:
                    key = reference.place_city_key(place_name)
                    city_counts[key] += 1
                    city_display.setdefault(key, reference.station_city_label(place_name))

        distance = 0.0
        longest_id: uuid.UUID | None = None
        longest_km = 0.0

        def consider(record_id: uuid.UUID, km: float) -> None:
            nonlocal longest_id, longest_km
            # Deterministic tie-break: more km wins, then the smaller id. The
            # old "first max in list_all order" rule has no stable equivalent
            # now that the full-table scan is gone.
            if km and (
                longest_id is None
                or km > longest_km
                or (km == longest_km and record_id < longest_id)
            ):
                longest_id, longest_km = record_id, km

        for record_id, stored in self._stored_distance_rows(user_id=user_id, record_ids=year_ids):
            km = float(stored)
            distance += km
            consider(record_id, km)
        for row in self._null_distance_rows(user_id=user_id, record_ids=year_ids):
            km = self._endpoint_distance_km(row.type, row.origin, row.destination)
            if km:
                distance += km
                consider(row.id, km)

        year_hotels = [
            (check_in, check_out) for check_in, check_out in hotel_rows if check_in.year == target
        ]
        nights = sum(
            (check_out - check_in).days for check_in, check_out in year_hotels if check_out
        )
        year_activities = sum(1 for day in activity_dates if day.year == target)
        year_expenses = self._expenses_by_ids(
            user_id=user_id,
            expense_ids=[
                expense_id for expense_id, day in expense_dates.items() if day.year == target
            ],
        )

        user = self.db.get(User, user_id)
        report_currency = (user.currency if user else None) or "CNY"

        longest_route = None
        if longest_id is not None:
            record = self.db.scalar(
                select(TransportRecord).where(
                    TransportRecord.id == longest_id,
                    TransportRecord.user_id == user_id,
                )
            )
            if record is not None:
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
                    distance_km=longest_km,
                    departure_date=year_days[record.id],
                )

        favorite_trip = None
        if trip_counts:
            trip_id, count = trip_counts[0]
            trip = self.db.scalar(select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id))
            if trip is not None:
                favorite_trip = BreakdownItem(label=trip.name, count=count)

        most_visited_city = None
        if city_counts:
            city_key, count = min(city_counts.items(), key=lambda item: (-item[1], item[0]))
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
                trips=len(trip_counts),
                flights=type_counts.get("flight", 0),
                trains=type_counts.get("train", 0),
                transports=type_counts.get("other", 0),
                hotels=len(year_hotels),
                hotel_nights=nights,
                activities=year_activities,
                travel_days=len(days),
            ),
            by_month=self._chronological(months),
            top_airlines=self._top_with_airline_names(
                self._airline_counts(user_id=user_id, record_ids=year_ids)
            ),
            top_airports=self._top_with_airport_names(
                self._endpoint_counts(
                    user_id=user_id,
                    record_type="flight",
                    record_ids=year_ids,
                )
            ),
            top_stations=self._items(
                self._endpoint_counts(
                    user_id=user_id,
                    record_type=("train", "other"),
                    record_ids=year_ids,
                )
            )[:5],
            top_aircraft=self._items(
                self._group_counts(
                    user_id=user_id,
                    record_type="flight",
                    column=TransportRecord.aircraft_model,
                    record_ids=year_ids,
                )
            )[:5],
            most_visited_city=most_visited_city,
            favorite_trip=favorite_trip,
            longest_route=longest_route,
            first_journey=min(days) if days else None,
            last_journey=max(days) if days else None,
            spend=summarize_expenses(year_expenses, report_currency),
        )

    @staticmethod
    def _top_with_airline_names(
        rows: list[tuple[str, int]], *, limit: int = 5
    ) -> list[BreakdownItem]:
        items: list[BreakdownItem] = []
        for code, count in rows[:limit]:
            airline = reference.get_airline_by_iata(code)
            items.append(
                BreakdownItem(
                    label=code, name=airline.get("name") if airline else None, count=count
                )
            )
        return items

    @staticmethod
    def _top_with_airport_names(
        rows: list[tuple[str, int]], *, limit: int = 5
    ) -> list[BreakdownItem]:
        items: list[BreakdownItem] = []
        for code, count in rows[:limit]:
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

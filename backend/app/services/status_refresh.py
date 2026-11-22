"""Time-based status progression for transport records, hotels and trips.

A journey whose end day has passed is completed by definition — unless the
user explicitly cancelled it. Instead of a scheduler, every read entry point
lazily materializes the transition (REST reads, AI tools, MCP reads, dashboard
and export), so statuses converge as soon as the user looks at their data.

Rules (forward-only; explicit user choices are never overwritten):

- transport ``scheduled`` → ``completed`` once the local calendar day of its
  end time (actual arrival → arrival → actual departure → departure) has fully
  passed in the record's timezone. Day-based rather than instant-based so a
  date-only entry (midnight timestamp) is not completed at 00:01 on the day of
  travel. Undated records stay ``scheduled``.
- hotel ``scheduled`` → ``completed`` once check-out (fallback check-in) is
  before today, matching the creation-time inference in ``HotelService``.
- trip ``planned`` → ``ongoing`` when the start date has arrived and the end
  has not passed; ``planned``/``ongoing`` → ``completed`` once end_date < today.
- ``cancelled`` and ``completed`` rows are never touched.

Transitions are derived state, not user actions, so they are not audited.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.timezones import in_timezone
from app.models.hotel import Hotel
from app.models.transport_record import TransportRecord
from app.models.trip import Trip

# SQLite has a bound-parameter limit; chunk bulk updates to stay portable.
_UPDATE_CHUNK = 500

_TIME_FIELDS = (
    ("actual_arrival_time", "arrival_timezone"),
    ("arrival_time", "arrival_timezone"),
    ("actual_departure_time", "departure_timezone"),
    ("departure_time", "departure_timezone"),
)


def transport_end(row: Any) -> tuple[datetime | None, str | None]:
    """End instant and its timezone, preferring actuals over scheduled times.

    Accepts an ORM row, a query Row or a plain payload dict so create/update
    inference and the read-time sweep share one definition of "the end".
    """
    for time_field, tz_field in _TIME_FIELDS:
        if isinstance(row, dict):
            value = row.get(time_field)
            zone = row.get(tz_field)
        else:
            value = getattr(row, time_field, None)
            zone = getattr(row, tz_field, None)
        if value is not None:
            return value, zone
    return None, None


def is_transport_expired(*, end_time: datetime | None, timezone: str | None, now: datetime) -> bool:
    """True once the end's local calendar day has fully passed.

    ``in_timezone`` treats naive (SQLite) datetimes as UTC and falls back to
    UTC for legacy/invalid zone names, so reads never fail on bad data.
    """
    if end_time is None:
        return False
    return in_timezone(end_time, timezone).date() < in_timezone(now, timezone).date()


def refresh_user_statuses(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
    today: date | None = None,
    commit: bool = True,
) -> dict[str, int]:
    """Materialize overdue statuses for one user; return per-table counts.

    Callers are read entry points with no pending write state: the sweep
    commits its own changes because GET transactions are never committed by
    the request lifecycle. Each UPDATE re-checks ``status`` so concurrent
    sweeps or user edits cannot clobber a newer choice.

    ``now`` defaults to the current UTC instant (transport day boundaries are
    evaluated per record timezone); ``today`` defaults to the server's calendar
    day for the date-only hotel/trip rules. Pass either explicitly for
    deterministic tests.
    """
    now = now or datetime.now(UTC)
    # Date-only entities follow the server's calendar day, exactly like the
    # creation-time inference in HotelService._infer_status.
    today = today or date.today()
    counts = {"transport": 0, "hotel": 0, "trip": 0}

    # Transport: per-row timezone math cannot be expressed portably in SQL
    # (SQLite ↔ Postgres), so normalize in Python like DashboardService does.
    # After the first sweep only genuinely upcoming rows remain candidates.
    rows = db.execute(
        select(
            TransportRecord.id,
            TransportRecord.actual_arrival_time,
            TransportRecord.arrival_time,
            TransportRecord.actual_departure_time,
            TransportRecord.departure_time,
            TransportRecord.arrival_timezone,
            TransportRecord.departure_timezone,
        ).where(TransportRecord.user_id == user_id, TransportRecord.status == "scheduled")
    ).all()
    expired = []
    for row in rows:
        end, zone = transport_end(row)
        if is_transport_expired(end_time=end, timezone=zone, now=now):
            expired.append(row.id)
    # Stable order so concurrent sweeps take row locks in the same sequence.
    expired.sort()
    for start in range(0, len(expired), _UPDATE_CHUNK):
        chunk = expired[start : start + _UPDATE_CHUNK]
        result = db.execute(
            update(TransportRecord)
            .where(TransportRecord.id.in_(chunk), TransportRecord.status == "scheduled")
            .values(status="completed")
        )
        counts["transport"] += result.rowcount or 0

    # Hotels and trips are date-only: a plain SQL comparison is portable.
    result = db.execute(
        update(Hotel)
        .where(
            Hotel.user_id == user_id,
            Hotel.status == "scheduled",
            func.coalesce(Hotel.check_out, Hotel.check_in) < today,
        )
        .values(status="completed")
    )
    counts["hotel"] = result.rowcount or 0

    result = db.execute(
        update(Trip)
        .where(
            Trip.user_id == user_id,
            Trip.status.in_(("planned", "ongoing")),
            Trip.end_date.isnot(None),
            Trip.end_date < today,
        )
        .values(status="completed")
    )
    counts["trip"] = result.rowcount or 0
    result = db.execute(
        update(Trip)
        .where(
            Trip.user_id == user_id,
            Trip.status == "planned",
            Trip.start_date.isnot(None),
            Trip.start_date <= today,
            or_(Trip.end_date.is_(None), Trip.end_date >= today),
        )
        .values(status="ongoing")
    )
    counts["trip"] += result.rowcount or 0

    if commit and any(counts.values()):
        db.commit()
    return counts

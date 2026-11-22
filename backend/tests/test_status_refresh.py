"""Time-based status progression (spec #11/#15/#17 status vocabularies).

A journey whose end day has passed must not stay ``scheduled`` forever: reads
lazily materialize ``scheduled → completed`` (and ``planned → ongoing →
completed`` for trips) without ever overwriting an explicit user choice.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models.audit_log import AuditAction, AuditLog
from app.models.hotel import Hotel
from app.models.transport_record import TransportRecord
from app.services.status_refresh import refresh_user_statuses
from tests.conftest import auth_headers, register_and_login

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _noon(day: date) -> str:
    return datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC).isoformat()


def _flight(client, headers, number: str, **overrides) -> dict:
    payload = {
        "origin": "PEK",
        "destination": "SHA",
        "service_number": number,
        "departure_time": _noon(TOMORROW),
        **overrides,
    }
    resp = client.post("/api/v1/flights", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_past_journey_is_born_completed(client):
    headers = _headers(client, "status_born")
    past = _flight(
        client,
        headers,
        "CA1001",
        departure_time=_noon(YESTERDAY),
        arrival_time=_noon(YESTERDAY),
    )
    assert past["status"] == "completed"
    future = _flight(client, headers, "CA1002")
    assert future["status"] == "scheduled"
    # Same rule for trains (shared TransportService).
    train = client.post(
        "/api/v1/trains",
        json={
            "origin": "北京南",
            "destination": "上海虹桥",
            "service_number": "G1",
            "departure_time": _noon(YESTERDAY),
        },
        headers=headers,
    )
    assert train.status_code == 201, train.text
    assert train.json()["status"] == "completed"


def test_explicit_statuses_are_never_overwritten(client):
    headers = _headers(client, "status_explicit")
    cancelled = _flight(
        client, headers, "CA1101", departure_time=_noon(YESTERDAY), status="cancelled"
    )
    completed = _flight(
        client, headers, "CA1102", departure_time=_noon(YESTERDAY), status="completed"
    )
    listed = client.get("/api/v1/flights", headers=headers).json()["items"]
    by_number = {f["service_number"]: f["status"] for f in listed}
    assert by_number["CA1101"] == "cancelled"
    assert by_number["CA1102"] == "completed"
    assert cancelled["status"] == "cancelled"
    assert completed["status"] == "completed"


def test_read_sweep_completes_legacy_scheduled_rows(client, db):
    headers = _headers(client, "status_sweep")
    row = _flight(client, headers, "CA1201")
    # Simulate a legacy row written before this feature: scheduled, but past.
    record = db.get(TransportRecord, uuid.UUID(row["id"]))
    record.departure_time = datetime.now(UTC) - timedelta(days=2)
    record.status = "scheduled"
    db.flush()

    got = client.get(f"/api/v1/flights/{row['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["status"] == "completed"
    db.refresh(record)
    assert record.status == "completed"  # persisted, not just rendered


def test_undated_record_stays_scheduled(client):
    headers = _headers(client, "status_undated")
    row = _flight(client, headers, "CA1301", departure_time=None)
    got = client.get(f"/api/v1/flights/{row['id']}", headers=headers)
    assert got.json()["status"] == "scheduled"


def test_day_boundary_uses_record_timezone(client, db):
    headers = _headers(client, "status_tz")
    # Fixed instants, 2h apart: 2026-06-14 22:00Z → 2026-06-15 00:00Z. In UTC
    # the end's day has passed; in +14 (Kiritimati) both are on 06-15, so the
    # day is not over yet. Same instant, different local calendar day.
    ahead = _flight(client, headers, "CA1401")
    behind = _flight(client, headers, "CA1402")
    end = datetime(2026, 6, 14, 22, 0, tzinfo=UTC)
    now = datetime(2026, 6, 15, 0, 0, tzinfo=UTC)
    rows = []
    for row_id, zone in ((ahead["id"], "Pacific/Kiritimati"), (behind["id"], None)):
        record = db.get(TransportRecord, uuid.UUID(row_id))
        record.departure_time = end
        record.departure_timezone = zone
        record.status = "scheduled"
        rows.append(record)
    db.flush()

    counts = refresh_user_statuses(db, rows[0].user_id, now=now, commit=False)
    assert counts["transport"] == 1
    assert rows[0].status == "scheduled"  # +14: still the same local day
    assert rows[1].status == "completed"  # UTC: the day has passed


def test_actual_arrival_wins_over_scheduled(client):
    headers = _headers(client, "status_actual")
    row = _flight(
        client,
        headers,
        "CA1501",
        departure_time=_noon(YESTERDAY),
        arrival_time=_noon(YESTERDAY),
        actual_arrival_time=_noon(TOMORROW),
    )
    assert row["status"] == "scheduled"
    got = client.get(f"/api/v1/flights/{row['id']}", headers=headers)
    assert got.json()["status"] == "scheduled"


def test_pinned_scheduled_is_recompleted_on_next_read(client):
    headers = _headers(client, "status_pin")
    row = _flight(client, headers, "CA1601", departure_time=_noon(YESTERDAY))
    assert row["status"] == "completed"
    # An explicit status in the request is honoured for that request…
    pinned = client.patch(
        f"/api/v1/flights/{row['id']}", json={"status": "scheduled"}, headers=headers
    )
    assert pinned.json()["status"] == "scheduled"
    # …but the next read materializes the passage of time again.
    got = client.get(f"/api/v1/flights/{row['id']}", headers=headers)
    assert got.json()["status"] == "completed"


def test_moving_times_into_the_past_completes_on_update(client):
    headers = _headers(client, "status_move")
    row = _flight(client, headers, "CA1701")
    assert row["status"] == "scheduled"
    updated = client.patch(
        f"/api/v1/flights/{row['id']}",
        json={"departure_time": _noon(YESTERDAY)},
        headers=headers,
    )
    assert updated.json()["status"] == "completed"


def test_hotel_sweep_and_checkout_day(client):
    headers = _headers(client, "status_hotel")
    stay = client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Test Inn",
            "check_in": TOMORROW.isoformat(),
            "check_out": (TOMORROW + timedelta(days=2)).isoformat(),
        },
        headers=headers,
    ).json()
    assert stay["status"] == "scheduled"
    # Move the stay into the past while pinning scheduled: the read sweep wins.
    client.patch(
        f"/api/v1/hotels/{stay['id']}",
        json={
            "check_in": (YESTERDAY - timedelta(days=1)).isoformat(),
            "check_out": YESTERDAY.isoformat(),
            "status": "scheduled",
        },
        headers=headers,
    )
    got = client.get(f"/api/v1/hotels/{stay['id']}", headers=headers)
    assert got.json()["status"] == "completed"

    # Checkout *today* is not over yet (matches creation-time inference).
    current = client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Current Inn",
            "check_in": YESTERDAY.isoformat(),
            "check_out": TODAY.isoformat(),
        },
        headers=headers,
    ).json()
    assert current["status"] == "scheduled"
    got = client.get(f"/api/v1/hotels/{current['id']}", headers=headers)
    assert got.json()["status"] == "scheduled"


def test_trip_progression(client):
    headers = _headers(client, "status_trip")

    def trip(name: str, **overrides) -> dict:
        resp = client.post("/api/v1/trips", json={"name": name, **overrides}, headers=headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    past = trip("Past", start_date=YESTERDAY.isoformat(), end_date=YESTERDAY.isoformat())
    trip("Spanning", start_date=YESTERDAY.isoformat(), end_date=TOMORROW.isoformat())
    trip("Future", start_date=TOMORROW.isoformat(), end_date=TOMORROW.isoformat())
    trip(
        "Cancelled",
        start_date=YESTERDAY.isoformat(),
        end_date=YESTERDAY.isoformat(),
        status="cancelled",
    )
    trip(
        "OngoingPast",
        start_date=YESTERDAY.isoformat(),
        end_date=YESTERDAY.isoformat(),
        status="ongoing",
    )
    trip("Undated")

    listed = client.get("/api/v1/trips", headers=headers).json()["items"]
    by_name = {t["name"]: t["status"] for t in listed}
    assert by_name == {
        "Past": "completed",
        "Spanning": "ongoing",
        "Future": "planned",
        "Cancelled": "cancelled",
        "OngoingPast": "completed",
        "Undated": "planned",
    }
    assert past["status"] == "planned"  # creation keeps the default; reads advance


def test_sweep_is_user_scoped(client, db):
    headers_a = _headers(client, "status_scope_a")
    headers_b = _headers(client, "status_scope_b")
    row = _flight(client, headers_a, "CA1801")
    record = db.get(TransportRecord, uuid.UUID(row["id"]))
    record.departure_time = datetime.now(UTC) - timedelta(days=2)
    record.status = "scheduled"
    db.flush()

    client.get("/api/v1/flights", headers=headers_b)
    db.refresh(record)
    assert record.status == "scheduled"  # another user's read must not touch it

    client.get("/api/v1/flights", headers=headers_a)
    db.refresh(record)
    assert record.status == "completed"


def test_refresh_counts_and_idempotency(client, db):
    headers = _headers(client, "status_counts")
    row = _flight(client, headers, "CA1901")
    record = db.get(TransportRecord, uuid.UUID(row["id"]))
    user_id = record.user_id
    record.departure_time = datetime.now(UTC) - timedelta(days=2)
    record.status = "scheduled"
    db.flush()

    counts = refresh_user_statuses(db, user_id, commit=False)
    assert counts["transport"] == 1
    again = refresh_user_statuses(db, user_id, commit=False)
    assert again == {"transport": 0, "hotel": 0, "trip": 0}


def test_sweep_logs_one_aggregated_audit_and_header(client, db):
    headers = _headers(client, "status_audit")
    flight = _flight(client, headers, "CA2001")
    hotel = client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Audit Inn",
            "check_in": TOMORROW.isoformat(),
            "check_out": (TOMORROW + timedelta(days=1)).isoformat(),
        },
        headers=headers,
    ).json()
    client.post(
        "/api/v1/trips",
        json={
            "name": "Audit Trip",
            "start_date": YESTERDAY.isoformat(),
            "end_date": YESTERDAY.isoformat(),
        },
        headers=headers,
    )
    # Age the flight and hotel via ORM so no intermediate request sweeps them
    # one by one: the next read must advance all three tables in ONE sweep.
    record = db.get(TransportRecord, uuid.UUID(flight["id"]))
    record.departure_time = datetime.now(UTC) - timedelta(days=2)
    record.status = "scheduled"
    stay = db.get(Hotel, uuid.UUID(hotel["id"]))
    stay.check_in = YESTERDAY - timedelta(days=1)
    stay.check_out = YESTERDAY
    stay.status = "scheduled"
    db.flush()

    resp = client.get("/api/v1/flights", headers=headers)
    assert resp.headers["x-status-updated"] == "3"
    entries = db.scalars(
        select(AuditLog).where(
            AuditLog.user_id == record.user_id,
            AuditLog.action == AuditAction.STATUS_AUTO_ADVANCED,
        )
    ).all()
    assert len(entries) == 1
    assert entries[0].meta == {"counts": {"transport": 1, "hotel": 1, "trip": 1}}
    assert entries[0].ip  # REST-triggered sweeps keep client traceability (#47)

    # Nothing left to advance: no header, no second audit row.
    resp2 = client.get("/api/v1/flights", headers=headers)
    assert "x-status-updated" not in resp2.headers
    entries2 = db.scalars(
        select(AuditLog).where(
            AuditLog.user_id == record.user_id,
            AuditLog.action == AuditAction.STATUS_AUTO_ADVANCED,
        )
    ).all()
    assert len(entries2) == 1


def test_no_audit_when_nothing_advances(client, db):
    headers = _headers(client, "status_noaudit")
    _flight(client, headers, "CA2101")  # future: stays scheduled
    resp = client.get("/api/v1/flights", headers=headers)
    assert "x-status-updated" not in resp.headers
    entries = db.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.STATUS_AUTO_ADVANCED)
    ).all()
    assert entries == []

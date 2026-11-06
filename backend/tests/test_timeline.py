"""Computed timeline: source-owned times, repair and timezones (docs §5)."""

import uuid

from sqlalchemy import delete, func, select

from app.models.trip_item import TripItem
from tests.conftest import auth_headers, register_and_login

FLIGHT = {
    "origin": "HKG",
    "destination": "NRT",
    "departure_time": "2026-04-29T01:45:00Z",
    "arrival_time": "2026-04-29T06:10:00Z",
    "carrier": "Cathay Pacific",
    "service_number": "CX524",
}

PLACE = {
    "type": "attraction",
    "city": "Singapore",
    "name": "Gardens by the Bay",
    "timezone": "Asia/Singapore",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _trip(client, headers, name="Tokyo 2026") -> dict:
    response = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _flight(client, headers, trip_id=None, **overrides) -> dict:
    payload = {**FLIGHT, **overrides}
    if trip_id:
        payload["trip_id"] = trip_id
    response = client.post("/api/v1/flights", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _detail(client, headers, trip_id) -> dict:
    response = client.get(f"/api/v1/trips/{trip_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_activity_timezone_defaults_from_place_then_explicit_wins(client):
    headers = _headers(client, "timeline_timezone")
    place = client.post("/api/v1/places", json=PLACE, headers=headers)
    assert place.status_code == 201, place.text
    place_id = place.json()["id"]

    response = client.post(
        "/api/v1/activities",
        json={"name": "Light show", "place_id": place_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["timezone"] == "Asia/Singapore"

    explicit = client.post(
        "/api/v1/activities",
        json={"name": "Late dinner", "place_id": place_id, "timezone": "Asia/Tokyo"},
        headers=headers,
    )
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["timezone"] == "Asia/Tokyo"


def test_hotel_items_use_date_semantics(client):
    headers = _headers(client, "timeline_hotel_dates")
    trip = _trip(client, headers)
    response = client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Narita Rest",
            "check_in": "2026-04-28",
            "check_out": "2026-04-30",
            "trip_id": trip["id"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text

    item = _detail(client, headers, trip["id"])["items"][0]
    assert item["time_kind"] == "date"
    assert item["start_date"] == "2026-04-28"
    assert item["end_date"] == "2026-04-30"
    assert item["start_at"] is None
    assert item["is_unscheduled"] is False


def test_unscheduled_records_sort_last(client):
    headers = _headers(client, "timeline_unscheduled")
    trip = _trip(client, headers)
    scheduled = _flight(client, headers, trip["id"])
    unscheduled = _flight(
        client,
        headers,
        trip["id"],
        departure_time=None,
        arrival_time=None,
        service_number="CX999",
    )

    items = _detail(client, headers, trip["id"])["items"]
    assert [item["item_id"] for item in items] == [scheduled["id"], unscheduled["id"]]
    assert items[1]["is_unscheduled"] is True
    assert items[1]["time_kind"] == "instant"


def test_get_never_repairs_a_missing_projection(client, db):
    headers = _headers(client, "timeline_no_self_heal")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])

    db.execute(delete(TripItem))
    db.flush()

    items = _detail(client, headers, trip["id"])["items"]
    # The source is still shown (nothing is hidden), but without an item id.
    assert [item["item_id"] for item in items] == [flight["id"]]
    assert items[0]["id"] is None
    assert db.scalar(select(func.count()).select_from(TripItem)) == 0

    repaired = client.post(f"/api/v1/trips/{trip['id']}/timeline/repair", headers=headers)
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["added"] == 1

    items = _detail(client, headers, trip["id"])["items"]
    assert items[0]["id"] is not None
    assert items[0]["item_id"] == flight["id"]


def test_repair_removes_projections_of_missing_sources(client, db):
    headers = _headers(client, "timeline_repair_stale")
    trip = _trip(client, headers)
    db.add(
        TripItem(
            user_id=uuid.UUID(_detail(client, headers, trip["id"])["user_id"]),
            trip_id=uuid.UUID(trip["id"]),
            item_type="transport",
            item_id=uuid.uuid4(),
            sort_order=0,
        )
    )
    db.flush()

    detail = _detail(client, headers, trip["id"])
    assert detail["items"] == []

    repaired = client.post(f"/api/v1/trips/{trip['id']}/timeline/repair", headers=headers)
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["removed"] == 1
    assert db.scalar(select(func.count()).select_from(TripItem)) == 0


def test_source_time_change_reorders_the_timeline(client):
    headers = _headers(client, "timeline_source_reorder")
    trip = _trip(client, headers)
    first = _flight(
        client,
        headers,
        trip["id"],
        departure_time="2026-04-29T01:00:00Z",
        arrival_time="2026-04-29T02:00:00Z",
        service_number="CX1",
    )
    second = _flight(
        client,
        headers,
        trip["id"],
        departure_time="2026-04-29T02:00:00Z",
        arrival_time="2026-04-29T03:00:00Z",
        service_number="CX2",
    )
    assert [i["item_id"] for i in _detail(client, headers, trip["id"])["items"]] == [
        first["id"],
        second["id"],
    ]

    response = client.patch(
        f"/api/v1/flights/{first['id']}",
        json={"departure_time": "2026-04-29T03:00:00Z"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    items = _detail(client, headers, trip["id"])["items"]
    assert [item["item_id"] for item in items] == [second["id"], first["id"]]
    assert [item["sort_order"] for item in items] == [0, 1]


def test_legacy_place_item_creates_a_visit_activity(client):
    headers = _headers(client, "timeline_legacy_place")
    trip = _trip(client, headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()

    added = client.post(
        f"/api/v1/trips/{trip['id']}/items",
        json={
            "item_type": "place",
            "item_id": place["id"],
            "start_at": "2026-04-30T10:00:00Z",
        },
        headers=headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["item_type"] == "activity"

    item = _detail(client, headers, trip["id"])["items"][0]
    assert item["item_type"] == "activity"
    assert item["time_kind"] == "instant"
    assert item["activity"]["type"] == "visit"
    assert item["activity"]["name"] == "Gardens by the Bay"
    assert item["activity"]["place_id"] == place["id"]
    assert item["timezone"] == "Asia/Singapore"
    assert item["start_at"] is not None


def test_trip_item_row_has_no_event_time_columns():
    """Stage 4 dropped the duplicated time columns (docs §10.5)."""
    columns = set(TripItem.__table__.columns.keys())
    assert "start_at" not in columns
    assert "end_at" not in columns

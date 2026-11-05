"""Activity CRUD, trip mirroring and place linkage (spec #18, #57)."""

import uuid

from sqlalchemy import select

from app.models.trip_item import TripItem
from tests.conftest import auth_headers, register_and_login

ACTIVITY = {
    "name": "Gardens by the Bay light show",
    "type": "sightseeing",
    "start_at": "2026-04-30T11:00:00Z",
    "end_at": "2026-04-30T12:30:00Z",
    "price": "18.00",
    "currency": "sgd",
    "notes": "Supertree Grove",
}

PLACE = {
    "type": "attraction",
    "city": "Singapore",
    "name": "Gardens by the Bay",
    "lat": 1.2816,
    "lon": 103.8636,
    "timezone": "Asia/Singapore",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _create_trip(client, headers: dict[str, str], name: str = "Singapore 2026") -> dict:
    resp = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_place(client, headers: dict[str, str], **overrides) -> dict:
    resp = client.post("/api/v1/places", json={**PLACE, **overrides}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_read_activity(client):
    headers = _headers(client, "activity_create")
    place = _create_place(client, headers)
    resp = client.post(
        "/api/v1/activities",
        json={**ACTIVITY, "place_id": place["id"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Gardens by the Bay light show"
    assert body["type"] == "sightseeing"
    assert body["currency"] == "SGD"  # normalized to upper case
    assert body["place_id"] == place["id"]

    got = client.get(f"/api/v1/activities/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["notes"] == "Supertree Grove"


def test_list_search_and_filters(client):
    headers = _headers(client, "activity_list")
    trip = _create_trip(client, headers)
    place = _create_place(client, headers)
    client.post(
        "/api/v1/activities",
        json={**ACTIVITY, "trip_id": trip["id"], "place_id": place["id"]},
        headers=headers,
    )
    client.post(
        "/api/v1/activities",
        json={
            **ACTIVITY,
            "name": "Laksa dinner",
            "type": "dining",
            "notes": "Maxwell Food Centre",
            "start_at": "2026-05-01T19:00:00Z",
            "end_at": None,
        },
        headers=headers,
    )

    assert client.get("/api/v1/activities", headers=headers).json()["total"] == 2

    found = client.get("/api/v1/activities", params={"search": "laksa"}, headers=headers).json()
    assert found["total"] == 1
    assert found["items"][0]["name"] == "Laksa dinner"

    dining = client.get("/api/v1/activities", params={"type": "dining"}, headers=headers).json()
    assert dining["total"] == 1

    by_trip = client.get(
        "/api/v1/activities", params={"trip_id": trip["id"]}, headers=headers
    ).json()
    assert by_trip["total"] == 1
    assert by_trip["items"][0]["trip_id"] == trip["id"]

    by_place = client.get(
        "/api/v1/activities", params={"place_id": place["id"]}, headers=headers
    ).json()
    assert by_place["total"] == 1


def test_update_activity(client):
    headers = _headers(client, "activity_update")
    created = client.post("/api/v1/activities", json=ACTIVITY, headers=headers).json()
    resp = client.patch(
        f"/api/v1/activities/{created['id']}",
        json={"name": "Light show at Supertree Grove", "end_at": "2026-04-30T13:00:00Z"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Light show at Supertree Grove"
    assert resp.json()["end_at"].startswith("2026-04-30T13:00:00")

    # name is NOT NULL: an explicit null must not wipe it.
    kept = client.patch(f"/api/v1/activities/{created['id']}", json={"name": None}, headers=headers)
    assert kept.status_code == 200
    assert kept.json()["name"] == "Light show at Supertree Grove"

    # Inverting the window via a single field is rejected with 400, not a 500.
    inverted = client.patch(
        f"/api/v1/activities/{created['id']}",
        json={"end_at": "2026-04-30T09:00:00Z"},
        headers=headers,
    )
    assert inverted.status_code == 400

    # create-time inversion is a validation error (422).
    bad = client.post(
        "/api/v1/activities",
        json={**ACTIVITY, "start_at": "2026-05-01T12:00:00Z", "end_at": "2026-05-01T09:00:00Z"},
        headers=headers,
    )
    assert bad.status_code == 422


def test_delete_activity(client):
    headers = _headers(client, "activity_delete")
    created = client.post("/api/v1/activities", json=ACTIVITY, headers=headers).json()
    assert client.delete(f"/api/v1/activities/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/activities/{created['id']}", headers=headers).status_code == 404


def test_user_isolation(client):
    a = _headers(client, "activity_iso_a")
    b = _headers(client, "activity_iso_b")
    created = client.post("/api/v1/activities", json=ACTIVITY, headers=a).json()

    assert client.get(f"/api/v1/activities/{created['id']}", headers=b).status_code == 404
    assert (
        client.patch(
            f"/api/v1/activities/{created['id']}", json={"notes": "x"}, headers=b
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/activities/{created['id']}", headers=b).status_code == 404
    assert client.get("/api/v1/activities", headers=b).json()["total"] == 0


def test_trip_assignment_syncs_timeline(client, db):
    headers = _headers(client, "activity_trip")
    trip = _create_trip(client, headers)
    later = client.post(
        "/api/v1/activities",
        json={**ACTIVITY, "trip_id": trip["id"]},
        headers=headers,
    )
    assert later.status_code == 201, later.text
    earlier = client.post(
        "/api/v1/activities",
        json={
            **ACTIVITY,
            "name": "Breakfast",
            "start_at": "2026-04-30T08:00:00Z",
            "end_at": "2026-04-30T09:00:00Z",
            "trip_id": trip["id"],
        },
        headers=headers,
    )
    assert earlier.status_code == 201, earlier.text

    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    activity_items = [i for i in detail["items"] if i["item_type"] == "activity"]
    assert [i["activity"]["name"] for i in activity_items] == [
        "Breakfast",
        "Gardens by the Bay light show",
    ]
    assert activity_items[1]["activity"]["id"] == later.json()["id"]

    # Editing times updates the mirrored item without moving its slot.
    item_id = activity_items[1]["id"]
    client.patch(
        f"/api/v1/activities/{later.json()['id']}",
        json={"end_at": "2026-04-30T14:00:00Z"},
        headers=headers,
    )
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    item = next(i for i in detail["items"] if i["id"] == item_id)
    assert item["end_at"].startswith("2026-04-30T14:00:00")

    # Detaching from the trip removes the timeline item.
    client.patch(
        f"/api/v1/activities/{later.json()['id']}",
        json={"trip_id": None},
        headers=headers,
    )
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert [i["activity"]["name"] for i in detail["items"] if i["item_type"] == "activity"] == [
        "Breakfast"
    ]
    assert (
        db.scalar(
            select(TripItem).where(
                TripItem.item_type == "activity",
                TripItem.item_id == uuid.UUID(later.json()["id"]),
            )
        )
        is None
    )


def test_delete_activity_removes_timeline_item(client):
    headers = _headers(client, "activity_trip_delete")
    trip = _create_trip(client, headers)
    created = client.post(
        "/api/v1/activities", json={**ACTIVITY, "trip_id": trip["id"]}, headers=headers
    ).json()

    assert client.delete(f"/api/v1/activities/{created['id']}", headers=headers).status_code == 204
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert detail["items"] == []


def test_trip_and_place_are_user_scoped(client):
    a = _headers(client, "activity_scope_a")
    b = _headers(client, "activity_scope_b")
    alice_trip = _create_trip(client, a, "Alice trip")
    alice_place = _create_place(client, a, name="Alice place")
    bob_trip = _create_trip(client, b, "Bob trip")
    bob_place = _create_place(client, b, name="Bob place")

    # Bob cannot attach an activity to Alice's trip…
    assert (
        client.post(
            "/api/v1/activities",
            json={**ACTIVITY, "trip_id": alice_trip["id"]},
            headers=b,
        ).status_code
        == 404
    )
    # …nor reference Alice's place.
    assert (
        client.post(
            "/api/v1/activities",
            json={**ACTIVITY, "place_id": alice_place["id"]},
            headers=b,
        ).status_code
        == 404
    )
    # Alice's own refs work.
    assert (
        client.post(
            "/api/v1/activities",
            json={**ACTIVITY, "trip_id": alice_trip["id"], "place_id": alice_place["id"]},
            headers=a,
        ).status_code
        == 201
    )

    # Updating to point at someone else's refs is a 404 too.
    created = client.post(
        "/api/v1/activities",
        json={**ACTIVITY, "trip_id": bob_trip["id"], "place_id": bob_place["id"]},
        headers=b,
    ).json()
    assert (
        client.patch(
            f"/api/v1/activities/{created['id']}",
            json={"trip_id": alice_trip["id"]},
            headers=b,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/activities/{created['id']}",
            json={"place_id": alice_place["id"]},
            headers=b,
        ).status_code
        == 404
    )


def test_deleting_place_detaches_activity(client):
    headers = _headers(client, "activity_place_delete")
    place = _create_place(client, headers)
    created = client.post(
        "/api/v1/activities", json={**ACTIVITY, "place_id": place["id"]}, headers=headers
    ).json()

    assert client.delete(f"/api/v1/places/{place['id']}", headers=headers).status_code == 204
    got = client.get(f"/api/v1/activities/{created['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["place_id"] is None


def test_deleting_trip_detaches_activity(client):
    headers = _headers(client, "activity_trip_delete2")
    trip = _create_trip(client, headers)
    created = client.post(
        "/api/v1/activities", json={**ACTIVITY, "trip_id": trip["id"]}, headers=headers
    ).json()

    assert client.delete(f"/api/v1/trips/{trip['id']}", headers=headers).status_code == 204
    got = client.get(f"/api/v1/activities/{created['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["trip_id"] is None


def test_audit_log(client):
    headers = _headers(client, "activity_audit")
    created = client.post("/api/v1/activities", json=ACTIVITY, headers=headers).json()
    client.delete(f"/api/v1/activities/{created['id']}", headers=headers)
    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    actions = {e["action"] for e in entries if e["resource_type"] == "activity"}
    assert "create_record" in actions
    assert "delete_record" in actions

"""Place CRUD and visit conversion (spec #14, #16, #57)."""

import uuid

from tests.conftest import auth_headers, register_and_login

PLACE = {
    "type": "attraction",
    "country": "Singapore",
    "region": None,
    "city": "Singapore",
    "district": "Marina South",
    "name": "Gardens by the Bay",
    "localized_name": "滨海湾花园",
    "lat": 1.2816,
    "lon": 103.8636,
    "timezone": "Asia/Singapore",
    "external_ids": {"osm": "way/123"},
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _create_trip(client, headers: dict[str, str], name: str = "Singapore 2026") -> dict:
    resp = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_read_place(client):
    headers = _headers(client, "place_create")
    resp = client.post("/api/v1/places", json=PLACE, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Gardens by the Bay"
    assert body["localized_name"] == "滨海湾花园"
    assert body["type"] == "attraction"
    assert body["external_ids"] == {"osm": "way/123"}

    got = client.get(f"/api/v1/places/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["lat"] == 1.2816
    assert got.json()["lon"] == 103.8636


def test_list_search_and_type_filter(client):
    headers = _headers(client, "place_list")
    client.post("/api/v1/places", json=PLACE, headers=headers)
    client.post(
        "/api/v1/places",
        json={**PLACE, "name": "Changi Airport", "type": "airport"},
        headers=headers,
    )

    assert client.get("/api/v1/places", headers=headers).json()["total"] == 2

    found = client.get("/api/v1/places", params={"search": "changi"}, headers=headers).json()
    assert found["total"] == 1
    assert found["items"][0]["name"] == "Changi Airport"

    airports = client.get("/api/v1/places", params={"type": "airport"}, headers=headers).json()
    assert airports["total"] == 1
    assert airports["items"][0]["type"] == "airport"


def test_update_place(client):
    headers = _headers(client, "place_update")
    created = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    resp = client.patch(
        f"/api/v1/places/{created['id']}",
        json={"localized_name": "滨海湾花园二期", "district": None, "name": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["localized_name"] == "滨海湾花园二期"
    # explicit null clears an optional field but never the required name
    assert body["district"] is None
    assert body["name"] == "Gardens by the Bay"


def test_coordinate_bounds_rejected(client):
    headers = _headers(client, "place_bounds")
    assert (
        client.post(
            "/api/v1/places", json={**PLACE, "name": "A", "lat": 95.0}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/places", json={**PLACE, "name": "B", "lon": 200.0}, headers=headers
        ).status_code
        == 422
    )


def test_user_isolation(client):
    a = _headers(client, "place_iso_a")
    b = _headers(client, "place_iso_b")
    created = client.post("/api/v1/places", json=PLACE, headers=a).json()

    assert client.get(f"/api/v1/places/{created['id']}", headers=b).status_code == 404
    assert (
        client.patch(f"/api/v1/places/{created['id']}", json={"city": "X"}, headers=b).status_code
        == 404
    )
    assert client.delete(f"/api/v1/places/{created['id']}", headers=b).status_code == 404
    assert client.get("/api/v1/places", headers=b).json()["total"] == 0


def test_delete_place_keeps_visit_activity(client):
    headers = _headers(client, "place_delete_item")
    trip = _create_trip(client, headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()

    added = client.post(
        f"/api/v1/trips/{trip['id']}/items",
        json={
            "item_type": "place",
            "item_id": place["id"],
            "start_at": "2026-04-30T10:00:00Z",
            "end_at": "2026-04-30T12:00:00Z",
        },
        headers=headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["activity"]["place_id"] == place["id"]

    assert client.delete(f"/api/v1/places/{place['id']}", headers=headers).status_code == 204
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert len(detail["items"]) == 1
    activity = detail["items"][0]["activity"]
    # The visit survives as a name snapshot without the dangling place link.
    assert activity["id"] == added.json()["activity"]["id"]
    assert activity["name"] == "Gardens by the Bay"
    assert activity["place_id"] is None


def test_add_and_remove_place_item_creates_a_visit(client):
    headers = _headers(client, "place_item")
    trip = _create_trip(client, headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    payload = {
        "item_type": "place",
        "item_id": place["id"],
        "start_at": "2026-04-30T10:00:00Z",
        "end_at": "2026-04-30T12:00:00Z",
    }

    added = client.post(f"/api/v1/trips/{trip['id']}/items", json=payload, headers=headers)
    assert added.status_code == 201, added.text
    item = added.json()
    assert item["item_type"] == "activity"
    assert item["activity"]["type"] == "visit"
    assert item["activity"]["place_id"] == place["id"]
    # The name is a snapshot of the place at creation time.
    assert item["activity"]["name"] == "Gardens by the Bay"
    assert item["activity"]["place"]["id"] == place["id"]
    assert item["activity"]["place"]["localized_name"] == "滨海湾花园"

    # The same place can be visited twice in one trip (docs §4.3).
    duplicate = client.post(f"/api/v1/trips/{trip['id']}/items", json=payload, headers=headers)
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["activity"]["id"] != item["activity"]["id"]

    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    visit_items = [i for i in detail["items"] if i["item_type"] == "activity"]
    assert len(visit_items) == 2
    assert all(i["activity"]["type"] == "visit" for i in visit_items)

    assert (
        client.delete(f"/api/v1/trips/{trip['id']}/items/{item['id']}", headers=headers).status_code
        == 204
    )
    assert len(client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()["items"]) == 1
    assert (
        client.delete(f"/api/v1/trips/{trip['id']}/items/{item['id']}", headers=headers).status_code
        == 404
    )


def test_add_place_item_is_user_scoped(client):
    a = _headers(client, "place_item_a")
    b = _headers(client, "place_item_b")
    trip = _create_trip(client, a, "Alice trip")
    bob_place = client.post("/api/v1/places", json={**PLACE, "name": "Bob place"}, headers=b).json()

    # Bob cannot add anything to Alice's trip…
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/items",
            json={"item_type": "place", "item_id": bob_place["id"]},
            headers=b,
        ).status_code
        == 404
    )
    # …and Alice cannot reference Bob's place.
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/items",
            json={"item_type": "place", "item_id": bob_place["id"]},
            headers=a,
        ).status_code
        == 404
    )
    # A place that does not exist is a 404 too.
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/items",
            json={"item_type": "place", "item_id": str(uuid.uuid4())},
            headers=a,
        ).status_code
        == 404
    )


def test_add_item_rejects_non_place_types(client):
    headers = _headers(client, "place_item_type")
    trip = _create_trip(client, headers)
    resp = client.post(
        f"/api/v1/trips/{trip['id']}/items",
        json={"item_type": "hotel", "item_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 422


def test_removing_mirrored_item_detaches_source_record(client):
    headers = _headers(client, "place_item_mirror")
    trip = _create_trip(client, headers)
    hotel = client.post(
        "/api/v1/hotels",
        json={"hotel": "Marina Bay Sands", "check_in": "2026-04-29", "trip_id": trip["id"]},
        headers=headers,
    ).json()
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    hotel_item = next(i for i in detail["items"] if i["item_type"] == "hotel")

    resp = client.delete(f"/api/v1/trips/{trip['id']}/items/{hotel_item['id']}", headers=headers)
    assert resp.status_code == 204

    # The trip no longer shows it, but the hotel record itself is kept.
    assert client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()["items"] == []
    kept = client.get(f"/api/v1/hotels/{hotel['id']}", headers=headers)
    assert kept.status_code == 200
    assert kept.json()["trip_id"] is None


def test_audit_log(client):
    headers = _headers(client, "place_audit")
    created = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    client.delete(f"/api/v1/places/{created['id']}", headers=headers)
    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    actions = {e["action"] for e in entries if e["resource_type"] == "place"}
    assert "create_record" in actions
    assert "delete_record" in actions

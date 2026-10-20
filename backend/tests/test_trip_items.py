from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models.trip_item import TripItem
from tests.conftest import auth_headers, register_and_login

TRIP = {"name": "Tokyo 2026"}


def _flight(trip_id: str | None = None, **overrides):
    data = {
        "origin": "HKG",
        "destination": "NRT",
        "departure_time": "2026-04-29T01:45:00Z",
        "arrival_time": "2026-04-29T06:10:00Z",
        "carrier": "Cathay Pacific",
        "service_number": "CX524",
    }
    if trip_id:
        data["trip_id"] = trip_id
    data.update(overrides)
    return data


def _trip(client, headers, name="Tokyo 2026"):
    response = client.post("/api/v1/trips", json={**TRIP, "name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _trip_detail(client, headers, trip_id):
    response = client.get(f"/api/v1/trips/{trip_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def test_trip_item_is_created_and_times_stay_in_sync(client):
    token = register_and_login(client, "item_sync")["access_token"]
    headers = auth_headers(token)

    trip = _trip(client, headers)
    flight = client.post("/api/v1/flights", json=_flight(trip["id"]), headers=headers)
    assert flight.status_code == 201, flight.text
    flight_id = flight.json()["id"]

    body = _trip_detail(client, headers, trip["id"])
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["item_type"] == "transport"
    assert item["item_id"] == flight_id
    assert item["record"]["id"] == flight_id
    assert item["sort_order"] == 0
    assert _parse(item["start_at"]) == _parse("2026-04-29T01:45:00Z")
    assert _parse(item["end_at"]) == _parse("2026-04-29T06:10:00Z")

    response = client.patch(
        f"/api/v1/flights/{flight_id}",
        json={"departure_time": "2026-04-29T02:00:00Z"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    item = _trip_detail(client, headers, trip["id"])["items"][0]
    assert _parse(item["start_at"]) == _parse("2026-04-29T02:00:00Z")


def test_moving_a_record_between_trips_moves_the_item(client):
    token = register_and_login(client, "item_move")["access_token"]
    headers = auth_headers(token)

    first = _trip(client, headers, "First")
    second = _trip(client, headers, "Second")
    flight = client.post("/api/v1/flights", json=_flight(first["id"]), headers=headers).json()

    response = client.patch(
        f"/api/v1/flights/{flight['id']}",
        json={"trip_id": second["id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    assert _trip_detail(client, headers, first["id"])["items"] == []
    items = _trip_detail(client, headers, second["id"])["items"]
    assert [item["item_id"] for item in items] == [flight["id"]]
    assert items[0]["sort_order"] == 0


def test_unassigning_and_deleting_records_remove_items(client, db):
    token = register_and_login(client, "item_remove")["access_token"]
    headers = auth_headers(token)

    trip = _trip(client, headers)
    flight = client.post("/api/v1/flights", json=_flight(trip["id"]), headers=headers).json()

    response = client.patch(
        f"/api/v1/flights/{flight['id']}", json={"trip_id": None}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert _trip_detail(client, headers, trip["id"])["items"] == []

    client.patch(f"/api/v1/flights/{flight['id']}", json={"trip_id": trip["id"]}, headers=headers)
    assert len(_trip_detail(client, headers, trip["id"])["items"]) == 1

    response = client.delete(f"/api/v1/flights/{flight['id']}", headers=headers)
    assert response.status_code == 204
    assert _trip_detail(client, headers, trip["id"])["items"] == []
    assert db.scalar(select(func.count()).select_from(TripItem)) == 0


def test_reorder_trip_items(client):
    token = register_and_login(client, "item_order")["access_token"]
    headers = auth_headers(token)

    trip = _trip(client, headers)
    flights = []
    for index, hour in enumerate((1, 2, 3)):
        flight = client.post(
            "/api/v1/flights",
            json=_flight(
                trip["id"],
                departure_time=f"2026-04-29T0{hour}:00:00Z",
                arrival_time=f"2026-04-29T{hour + 4:02d}:00:00Z",
                service_number=f"CX{index}",
            ),
            headers=headers,
        )
        assert flight.status_code == 201, flight.text
        flights.append(flight.json()["id"])

    items = _trip_detail(client, headers, trip["id"])["items"]
    assert [item["item_id"] for item in items] == flights

    reversed_ids = [item["id"] for item in reversed(items)]
    response = client.put(
        f"/api/v1/trips/{trip['id']}/items/order",
        json={"item_ids": reversed_ids},
        headers=headers,
    )
    assert response.status_code == 204, response.text

    items = _trip_detail(client, headers, trip["id"])["items"]
    assert [item["id"] for item in items] == reversed_ids
    assert [item["sort_order"] for item in items] == [0, 1, 2]


def test_reorder_rejects_incomplete_or_foreign_items(client):
    token = register_and_login(client, "item_order_bad")["access_token"]
    headers = auth_headers(token)

    trip = _trip(client, headers)
    client.post("/api/v1/flights", json=_flight(trip["id"]), headers=headers)
    items = _trip_detail(client, headers, trip["id"])["items"]

    response = client.put(
        f"/api/v1/trips/{trip['id']}/items/order",
        json={"item_ids": []},
        headers=headers,
    )
    assert response.status_code == 400

    other = _trip(client, headers, "Other")
    response = client.put(
        f"/api/v1/trips/{trip['id']}/items/order",
        json={"item_ids": [items[0]["id"], "00000000-0000-0000-0000-000000000000"]},
        headers=headers,
    )
    assert response.status_code == 400
    assert other["id"] != trip["id"]


def test_update_trip_item_bounds(client):
    token = register_and_login(client, "item_bounds")["access_token"]
    headers = auth_headers(token)

    trip = _trip(client, headers)
    client.post("/api/v1/flights", json=_flight(trip["id"]), headers=headers)
    item = _trip_detail(client, headers, trip["id"])["items"][0]

    response = client.patch(
        f"/api/v1/trips/{trip['id']}/items/{item['id']}",
        json={"start_at": "2026-04-29T00:30:00Z", "end_at": "2026-04-29T07:00:00Z"},
        headers=headers,
    )
    assert response.status_code == 204, response.text

    updated = _trip_detail(client, headers, trip["id"])["items"][0]
    assert _parse(updated["start_at"]) == _parse("2026-04-29T00:30:00Z")
    assert _parse(updated["end_at"]) == _parse("2026-04-29T07:00:00Z")

    response = client.patch(
        f"/api/v1/trips/{trip['id']}/items/00000000-0000-0000-0000-000000000000",
        json={"sort_order": 1},
        headers=headers,
    )
    assert response.status_code == 404


def test_deleting_a_trip_removes_items_but_keeps_records(client, db):
    token = register_and_login(client, "item_trip_delete")["access_token"]
    headers = auth_headers(token)

    trip = _trip(client, headers)
    flight = client.post("/api/v1/flights", json=_flight(trip["id"]), headers=headers).json()

    response = client.delete(f"/api/v1/trips/{trip['id']}", headers=headers)
    assert response.status_code == 204

    assert db.scalar(select(func.count()).select_from(TripItem)) == 0
    record = client.get(f"/api/v1/flights/{flight['id']}", headers=headers).json()
    assert record["trip_id"] is None


def test_cannot_assign_records_to_another_users_trip(client):
    token_a = register_and_login(client, "trip_owner_a")["access_token"]
    token_b = register_and_login(client, "trip_owner_b")["access_token"]
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    trip = _trip(client, headers_a)

    response = client.post("/api/v1/flights", json=_flight(trip["id"]), headers=headers_b)
    assert response.status_code == 404

    flight = client.post("/api/v1/flights", json=_flight(), headers=headers_b)
    assert flight.status_code == 201, flight.text
    response = client.patch(
        f"/api/v1/flights/{flight.json()['id']}",
        json={"trip_id": trip["id"]},
        headers=headers_b,
    )
    assert response.status_code == 404
    assert _trip_detail(client, headers_a, trip["id"])["items"] == []


def test_trip_item_routes_are_user_scoped(client):
    token_a = register_and_login(client, "item_owner")["access_token"]
    token_b = register_and_login(client, "item_intruder")["access_token"]

    trip = _trip(client, auth_headers(token_a))
    client.post("/api/v1/flights", json=_flight(trip["id"]), headers=auth_headers(token_a))
    item = _trip_detail(client, auth_headers(token_a), trip["id"])["items"][0]

    response = client.put(
        f"/api/v1/trips/{trip['id']}/items/order",
        json={"item_ids": [item["id"]]},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404

    response = client.patch(
        f"/api/v1/trips/{trip['id']}/items/{item['id']}",
        json={"sort_order": 0},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404

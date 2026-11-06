"""Visit/activity creation is safe to retry with an Idempotency-Key (docs §4.3, §9.1)."""

import uuid

from tests.conftest import auth_headers, register_and_login

PLACE = {
    "type": "attraction",
    "city": "Singapore",
    "name": "Gardens by the Bay",
    "timezone": "Asia/Singapore",
}

ACTIVITY = {
    "name": "Light show",
    "type": "sightseeing",
    "start_at": "2026-04-30T11:00:00Z",
    "end_at": "2026-04-30T12:30:00Z",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _trip(client, headers, name="Singapore 2026") -> dict:
    response = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _key() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


def test_legacy_place_retry_returns_the_same_visit(client):
    headers = _headers(client, "idem_place")
    trip = _trip(client, headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    payload = {
        "item_type": "place",
        "item_id": place["id"],
        "start_at": "2026-04-30T10:00:00Z",
    }
    key = _key()

    first = client.post(
        f"/api/v1/trips/{trip['id']}/items", json=payload, headers={**headers, **key}
    )
    second = client.post(
        f"/api/v1/trips/{trip['id']}/items", json=payload, headers={**headers, **key}
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["activity"]["id"] == second.json()["activity"]["id"]

    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert len(detail["items"]) == 1


def test_same_key_with_a_different_body_is_a_conflict(client):
    headers = _headers(client, "idem_conflict")
    trip = _trip(client, headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    key = _key()
    payload = {"item_type": "place", "item_id": place["id"]}

    first = client.post(
        f"/api/v1/trips/{trip['id']}/items", json=payload, headers={**headers, **key}
    )
    assert first.status_code == 201, first.text

    changed = {**payload, "start_at": "2026-04-30T10:00:00Z"}
    response = client.post(
        f"/api/v1/trips/{trip['id']}/items", json=changed, headers={**headers, **key}
    )
    assert response.status_code == 409, response.text


def test_activity_retry_does_not_create_a_second_event(client):
    headers = _headers(client, "idem_activity")
    trip = _trip(client, headers)
    key = _key()

    first = client.post(
        "/api/v1/activities", json={**ACTIVITY, "trip_id": trip["id"]}, headers={**headers, **key}
    )
    second = client.post(
        "/api/v1/activities", json={**ACTIVITY, "trip_id": trip["id"]}, headers={**headers, **key}
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    listing = client.get("/api/v1/activities", params={"trip_id": trip["id"]}, headers=headers)
    assert listing.json()["total"] == 1


def test_key_is_user_scoped(client):
    alice = _headers(client, "idem_alice")
    bob = _headers(client, "idem_bob")
    key = _key()

    first = client.post("/api/v1/activities", json=ACTIVITY, headers={**alice, **key})
    second = client.post("/api/v1/activities", json=ACTIVITY, headers={**bob, **key})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]


def test_deleted_result_blocks_replay(client):
    headers = _headers(client, "idem_deleted")
    key = _key()
    created = client.post("/api/v1/activities", json=ACTIVITY, headers={**headers, **key})
    assert created.status_code == 201, created.text
    activity_id = created.json()["id"]

    assert client.delete(f"/api/v1/activities/{activity_id}", headers=headers).status_code == 204
    replay = client.post("/api/v1/activities", json=ACTIVITY, headers={**headers, **key})
    assert replay.status_code == 409, replay.text


def test_without_a_key_retries_are_not_deduplicated(client):
    headers = _headers(client, "idem_no_key")
    first = client.post("/api/v1/activities", json=ACTIVITY, headers=headers)
    second = client.post("/api/v1/activities", json=ACTIVITY, headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]


EXPENSE = {"category": "food", "amount": "12.50", "currency": "EUR"}


def test_expense_retry_does_not_create_a_second_spend(client):
    headers = _headers(client, "idem_expense")
    key = _key()

    first = client.post("/api/v1/expenses", json=EXPENSE, headers={**headers, **key})
    second = client.post("/api/v1/expenses", json=EXPENSE, headers={**headers, **key})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    listing = client.get("/api/v1/expenses", headers=headers)
    assert listing.json()["total"] == 1


def test_expense_key_with_a_different_body_is_a_conflict(client):
    headers = _headers(client, "idem_expense_conflict")
    key = _key()

    first = client.post("/api/v1/expenses", json=EXPENSE, headers={**headers, **key})
    assert first.status_code == 201, first.text

    changed = {**EXPENSE, "amount": "99.00"}
    response = client.post("/api/v1/expenses", json=changed, headers={**headers, **key})
    assert response.status_code == 409, response.text


def test_expense_retry_with_a_source_returns_the_same_row(client):
    headers = _headers(client, "idem_expense_source")
    trip = _trip(client, headers)
    hotel = client.post(
        "/api/v1/hotels",
        json={"hotel": "Hotel", "check_in": "2026-08-02", "trip_id": trip["id"]},
        headers=headers,
    )
    assert hotel.status_code == 201, hotel.text
    payload = {
        "category": "accommodation",
        "amount": "100.00",
        "currency": "EUR",
        "source_type": "hotel",
        "source_id": hotel.json()["id"],
    }
    key = _key()

    first = client.post("/api/v1/expenses", json=payload, headers={**headers, **key})
    second = client.post("/api/v1/expenses", json=payload, headers={**headers, **key})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["trip_id"] == trip["id"]

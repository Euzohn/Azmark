"""Expenses linked to their source record (docs/data-model.md §6.3–6.6)."""

import uuid

from sqlalchemy import select

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

HOTEL = {
    "hotel": "Marina Bay Sands",
    "check_in": "2026-04-29",
    "check_out": "2026-05-02",
}

SPEND = {"category": "transport", "amount": "100.00", "currency": "SGD"}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _trip(client, headers, name="Singapore 2026") -> dict:
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


def _hotel(client, headers, trip_id=None, **overrides) -> dict:
    payload = {**HOTEL, **overrides}
    if trip_id:
        payload["trip_id"] = trip_id
    response = client.post("/api/v1/hotels", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _expense(client, headers, **overrides) -> dict:
    response = client.post("/api/v1/expenses", json={**SPEND, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_linked_expense_derives_and_follows_the_source_trip(client):
    headers = _headers(client, "expense_source_follow")
    trip = _trip(client, headers)
    other = _trip(client, headers, "Other")
    flight = _flight(client, headers, trip["id"])

    expense = _expense(
        client,
        headers,
        source_type="transport",
        source_id=flight["id"],
    )
    assert expense["trip_id"] == trip["id"]
    assert expense["source_type"] == "transport"
    assert expense["source_id"] == flight["id"]

    # Moving the record moves its spend along with it.
    moved = client.patch(
        f"/api/v1/flights/{flight['id']}", json={"trip_id": other["id"]}, headers=headers
    )
    assert moved.status_code == 200, moved.text
    got = client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()
    assert got["trip_id"] == other["id"]

    # Source filters are user-scoped.
    filtered = client.get(
        "/api/v1/expenses",
        params={"source_type": "transport", "source_id": flight["id"]},
        headers=headers,
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == expense["id"]


def test_bound_expense_rejects_a_conflicting_trip(client):
    headers = _headers(client, "expense_source_conflict")
    trip = _trip(client, headers)
    other = _trip(client, headers, "Other")
    hotel = _hotel(client, headers, trip["id"])

    response = client.post(
        "/api/v1/expenses",
        json={
            **SPEND,
            "source_type": "hotel",
            "source_id": hotel["id"],
            "trip_id": other["id"],
        },
        headers=headers,
    )
    assert response.status_code == 422, response.text

    created = _expense(client, headers, source_type="hotel", source_id=hotel["id"])
    response = client.patch(
        f"/api/v1/expenses/{created['id']}", json={"trip_id": other["id"]}, headers=headers
    )
    assert response.status_code == 422, response.text
    assert (
        client.get(f"/api/v1/expenses/{created['id']}", headers=headers).json()["trip_id"]
        == trip["id"]
    )


def test_source_pair_must_be_complete_and_owned(client):
    headers = _headers(client, "expense_source_pair")
    intruder = _headers(client, "expense_source_intruder")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])

    response = client.post(
        "/api/v1/expenses", json={**SPEND, "source_type": "transport"}, headers=headers
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/expenses",
        json={**SPEND, "source_type": "transport", "source_id": flight["id"]},
        headers=intruder,
    )
    assert response.status_code == 404

    response = client.post(
        "/api/v1/expenses",
        json={
            **SPEND,
            "source_type": "activity",
            "source_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=headers,
    )
    assert response.status_code == 404


def test_rebind_and_unbind_keep_a_sensible_trip(client):
    headers = _headers(client, "expense_source_rebind")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])
    hotel = _hotel(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="transport", source_id=flight["id"])

    rebound = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"source_type": "hotel", "source_id": hotel["id"]},
        headers=headers,
    )
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()["source_type"] == "hotel"
    assert rebound.json()["trip_id"] == trip["id"]

    # Unbinding keeps the trip snapshot so historical reports do not lose it.
    unbound = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"source_type": None, "source_id": None},
        headers=headers,
    )
    assert unbound.status_code == 200, unbound.text
    assert unbound.json()["source_type"] is None
    assert unbound.json()["source_id"] is None
    assert unbound.json()["trip_id"] == trip["id"]


def test_delete_source_keeps_the_expense_and_its_trip(client):
    headers = _headers(client, "expense_source_delete")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="transport", source_id=flight["id"])

    assert client.delete(f"/api/v1/flights/{flight['id']}", headers=headers).status_code == 204
    kept = client.get(f"/api/v1/expenses/{expense['id']}", headers=headers)
    assert kept.status_code == 200
    assert kept.json()["trip_id"] == trip["id"]
    assert kept.json()["source_type"] is None
    assert kept.json()["source_id"] is None


def test_removing_the_item_detaches_spend_from_the_trip(client):
    headers = _headers(client, "expense_source_unassign")
    trip = _trip(client, headers)
    handle = _hotel(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="hotel", source_id=handle["id"])
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    item = next(i for i in detail["items"] if i["item_type"] == "hotel")

    response = client.delete(f"/api/v1/trips/{trip['id']}/items/{item['id']}", headers=headers)
    assert response.status_code == 204, response.text

    got = client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()
    assert got["trip_id"] is None
    # The source link is kept; only the trip assignment was removed.
    assert got["source_type"] == "hotel"
    assert got["source_id"] == handle["id"]


def test_deleting_a_trip_clears_the_expense_trip(client):
    headers = _headers(client, "expense_source_trip_delete")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="transport", source_id=flight["id"])

    assert client.delete(f"/api/v1/trips/{trip['id']}", headers=headers).status_code == 204
    got = client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()
    assert got["trip_id"] is None
    assert got["source_id"] == flight["id"]


def test_bound_expense_cannot_drop_its_trip(client):
    headers = _headers(client, "expense_source_null_trip")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="transport", source_id=flight["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}", json={"trip_id": None}, headers=headers
    )
    assert response.status_code == 422, response.text
    assert (
        client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()["trip_id"]
        == trip["id"]
    )


def test_removing_a_stale_projection_keeps_the_source_trip(client, db):
    headers = _headers(client, "expense_source_stale")
    trip = _trip(client, headers)
    other = _trip(client, headers, "Other")
    flight = _flight(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="transport", source_id=flight["id"])

    projection = db.scalar(select(TripItem).where(TripItem.item_id == uuid.UUID(flight["id"])))
    assert projection is not None
    projection.trip_id = uuid.UUID(other["id"])
    db.flush()

    response = client.delete(f"/api/v1/trips/{other['id']}/items/{projection.id}", headers=headers)
    assert response.status_code == 204, response.text

    # The stale row is gone, but the record and its spend stay in their trip.
    assert (
        client.get(f"/api/v1/flights/{flight['id']}", headers=headers).json()["trip_id"]
        == trip["id"]
    )
    assert (
        client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()["trip_id"]
        == trip["id"]
    )


def test_trip_detail_reports_expenses_and_multi_currency_summary(client):
    headers = _headers(client, "expense_summary")
    trip = _trip(client, headers)
    _expense(client, headers, trip_id=trip["id"], amount="100.00", currency="CNY")
    _expense(client, headers, trip_id=trip["id"], amount="25.00", currency="SGD")
    _expense(
        client,
        headers,
        trip_id=trip["id"],
        amount="10.00",
        currency="SGD",
        converted_amount="54.00",
        converted_currency="CNY",
        exchange_rate="5.4",
    )

    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert len(detail["expenses"]) == 3
    summary = detail["expense_summary"]
    assert summary["report_currency"] == "CNY"
    assert float(summary["converted_total"]) == 154.0
    assert summary["converted_count"] == 2
    assert summary["unconverted_count"] == 1
    assert summary["unconverted"] == [{"currency": "SGD", "amount": "25.00"}]


def test_changing_the_amount_drops_a_stale_conversion(client):
    headers = _headers(client, "expense_conversion_reset")
    created = _expense(
        client,
        headers,
        converted_amount="54.00",
        converted_currency="CNY",
        exchange_rate="5.4",
    )
    updated = client.patch(
        f"/api/v1/expenses/{created['id']}", json={"amount": "20.00"}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["converted_amount"] is None
    assert body["converted_currency"] is None
    assert body["exchange_rate"] is None


def test_expense_id_is_returned_as_uuid(client):
    headers = _headers(client, "expense_source_uuid")
    trip = _trip(client, headers)
    flight = _flight(client, headers, trip["id"])
    expense = _expense(client, headers, source_type="transport", source_id=flight["id"])
    uuid.UUID(expense["id"])
    uuid.UUID(expense["source_id"])

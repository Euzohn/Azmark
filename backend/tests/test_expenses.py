"""Expense CRUD, filtering and user isolation (spec #19, #57)."""

import uuid
from datetime import date

from sqlalchemy import select

from app.models.expense import Expense
from tests.conftest import auth_headers, register_and_login

EXPENSE = {
    "category": "food",
    "amount": "12.50",
    "currency": "sgd",
    "description": "Lunch at Maxwell Food Centre",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def test_create_and_read_expense(client):
    headers = _headers(client, "expense_create")
    resp = client.post("/api/v1/expenses", json=EXPENSE, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert float(body["amount"]) == 12.5
    assert body["currency"] == "SGD"  # normalized to upper case
    assert body["occurred_at"] is not None  # defaults to "now"

    got = client.get(f"/api/v1/expenses/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["description"] == "Lunch at Maxwell Food Centre"


def test_amount_and_currency_are_required(client):
    headers = _headers(client, "expense_required")
    no_amount = client.post("/api/v1/expenses", json={"currency": "USD"}, headers=headers)
    assert no_amount.status_code == 422
    no_currency = client.post("/api/v1/expenses", json={"amount": "10"}, headers=headers)
    assert no_currency.status_code == 422
    bad_currency = client.post(
        "/api/v1/expenses", json={"amount": "10", "currency": "US"}, headers=headers
    )
    assert bad_currency.status_code == 422


def test_invalid_category_rejected(client):
    headers = _headers(client, "expense_category")
    resp = client.post(
        "/api/v1/expenses",
        json={**EXPENSE, "category": "bribes"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_list_search_and_category_filter(client):
    headers = _headers(client, "expense_list")
    client.post("/api/v1/expenses", json=EXPENSE, headers=headers)
    client.post(
        "/api/v1/expenses",
        json={
            "category": "transport",
            "amount": "30.00",
            "currency": "SGD",
            "description": "MRT top-up",
        },
        headers=headers,
    )
    assert client.get("/api/v1/expenses", headers=headers).json()["total"] == 2

    found = client.get("/api/v1/expenses", params={"search": "maxwell"}, headers=headers).json()
    assert found["total"] == 1
    assert found["items"][0]["description"] == "Lunch at Maxwell Food Centre"

    by_category = client.get(
        "/api/v1/expenses", params={"category": "transport"}, headers=headers
    ).json()
    assert by_category["total"] == 1
    assert by_category["items"][0]["category"] == "transport"


def test_date_range_filter(client):
    headers = _headers(client, "expense_dates")
    client.post(
        "/api/v1/expenses",
        json={**EXPENSE, "occurred_at": "2026-04-29T12:00:00Z"},
        headers=headers,
    )
    client.post(
        "/api/v1/expenses",
        json={**EXPENSE, "description": "May spend", "occurred_at": "2026-05-03T12:00:00Z"},
        headers=headers,
    )
    april = client.get(
        "/api/v1/expenses",
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
        headers=headers,
    ).json()
    assert april["total"] == 1
    assert april["items"][0]["description"] == "Lunch at Maxwell Food Centre"


def test_update_expense(client):
    headers = _headers(client, "expense_update")
    created = client.post("/api/v1/expenses", json=EXPENSE, headers=headers).json()
    resp = client.patch(
        f"/api/v1/expenses/{created['id']}",
        json={"amount": "99.90", "category": "shopping"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert float(resp.json()["amount"]) == 99.9
    assert resp.json()["category"] == "shopping"
    assert resp.json()["description"] == EXPENSE["description"]


def test_explicit_null_does_not_wipe_required_fields(client):
    headers = _headers(client, "expense_null")
    created = client.post("/api/v1/expenses", json=EXPENSE, headers=headers).json()
    resp = client.patch(
        f"/api/v1/expenses/{created['id']}",
        json={"amount": None, "currency": None, "description": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert float(resp.json()["amount"]) == 12.5
    assert resp.json()["currency"] == "SGD"
    assert resp.json()["description"] is None


def test_delete_expense(client, db):
    headers = _headers(client, "expense_delete")
    created = client.post("/api/v1/expenses", json=EXPENSE, headers=headers).json()
    assert client.delete(f"/api/v1/expenses/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/expenses/{created['id']}", headers=headers).status_code == 404
    assert db.scalar(select(Expense)) is None


def test_user_isolation(client):
    a = _headers(client, "expense_iso_a")
    b = _headers(client, "expense_iso_b")
    created = client.post("/api/v1/expenses", json=EXPENSE, headers=a).json()
    assert client.get(f"/api/v1/expenses/{created['id']}", headers=b).status_code == 404
    assert (
        client.patch(
            f"/api/v1/expenses/{created['id']}", json={"amount": "1"}, headers=b
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/expenses/{created['id']}", headers=b).status_code == 404
    assert client.get("/api/v1/expenses", headers=b).json()["total"] == 0


def test_trip_assignment_and_foreign_trip_rejected(client):
    a = _headers(client, "expense_trip_a")
    b = _headers(client, "expense_trip_b")
    trip = client.post("/api/v1/trips", json={"name": "Singapore 2026"}, headers=a).json()
    linked = client.post("/api/v1/expenses", json={**EXPENSE, "trip_id": trip["id"]}, headers=a)
    assert linked.status_code == 201, linked.text
    assert linked.json()["trip_id"] == trip["id"]

    per_trip = client.get("/api/v1/expenses", params={"trip_id": trip["id"]}, headers=a).json()
    assert per_trip["total"] == 1

    foreign = client.post("/api/v1/expenses", json={**EXPENSE, "trip_id": trip["id"]}, headers=b)
    assert foreign.status_code == 404


def test_audit_log(client):
    headers = _headers(client, "expense_audit")
    created = client.post("/api/v1/expenses", json=EXPENSE, headers=headers).json()
    client.delete(f"/api/v1/expenses/{created['id']}", headers=headers)
    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    actions = {e["action"] for e in entries if e["resource_type"] == "expense"}
    assert "create_record" in actions
    assert "delete_record" in actions


def test_read_token_cannot_create(client):
    headers = _headers(client, "expense_readtoken")
    secret = client.post(
        "/api/v1/tokens", json={"name": "ro", "scope": "read"}, headers=headers
    ).json()["token"]
    assert (
        client.post("/api/v1/expenses", json=EXPENSE, headers=auth_headers(secret)).status_code
        == 403
    )


def test_converted_amount_roundtrip(client, db):
    headers = _headers(client, "expense_convert")
    resp = client.post(
        "/api/v1/expenses",
        json={
            **EXPENSE,
            "converted_amount": "9.20",
            "converted_currency": "usd",
            "exchange_rate": "0.736",
            "exchange_rate_date": "2026-04-29",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert float(body["converted_amount"]) == 9.2
    assert body["converted_currency"] == "USD"
    assert body["exchange_rate_date"] == "2026-04-29"
    row = db.scalar(select(Expense).where(Expense.id == uuid.UUID(body["id"])))
    assert row is not None
    assert row.exchange_rate_date == date(2026, 4, 29)

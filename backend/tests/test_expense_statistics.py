"""Statistics-page spend aggregates (spec #28, docs §6.6)."""

import uuid
from datetime import UTC, datetime

from app.schemas.expense import ExpenseBreakdownItem
from tests.conftest import auth_headers, register_and_login


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _trip(client, headers, name: str) -> str:
    resp = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _expense(client, headers, **overrides) -> dict:
    payload = {"category": "other", "amount": "10.00", "currency": "CNY", **overrides}
    resp = client.post("/api/v1/expenses", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _stats(client, headers) -> dict:
    resp = client.get("/api/v1/statistics", headers=headers)
    assert resp.status_code == 200
    return resp.json()["expense_stats"]


def _bucket(items: list[dict], label: str) -> dict:
    return next(item for item in items if item["label"] == label)


def _bucket_model(items: list[ExpenseBreakdownItem], label: str) -> ExpenseBreakdownItem:
    return next(item for item in items if item.label == label)


def test_expense_statistics_buckets(client):
    headers = _headers(client, "stats_spend")
    trip = _trip(client, headers, "Beijing 2026")

    _expense(
        client,
        headers,
        category="transport",
        amount="100.00",
        trip_id=trip,
        occurred_at="2026-01-05T02:30:00Z",
    )
    _expense(
        client,
        headers,
        category="accommodation",
        amount="200.00",
        trip_id=trip,
        occurred_at="2026-01-06T02:30:00Z",
    )
    _expense(
        client,
        headers,
        category="food",
        amount="50.00",
        trip_id=trip,
        occurred_at="2026-02-10T02:30:00Z",
    )
    # Unconvertible foreign spend: counted, but never added to the CNY total.
    _expense(
        client,
        headers,
        category="shopping",
        amount="100.00",
        currency="USD",
        trip_id=trip,
        occurred_at="2026-02-11T02:30:00Z",
    )

    stats = _stats(client, headers)

    assert stats["report_currency"] == "CNY"
    assert stats["total"] == "350.00"
    assert stats["count"] == 4
    assert stats["converted_count"] == 3
    assert stats["unconverted_count"] == 1
    assert stats["average"] == "116.67"
    assert stats["largest"] == "200.00"

    assert _bucket(stats["by_category"], "transport")["amount"] == "100.00"
    assert _bucket(stats["by_category"], "accommodation")["amount"] == "200.00"
    assert _bucket(stats["by_category"], "food")["amount"] == "50.00"
    # Fixed vocabulary order: transport before accommodation before food.
    assert [item["label"] for item in stats["by_category"]] == [
        "transport",
        "accommodation",
        "food",
        "shopping",
    ]

    # Monthly buckets are chronological (the chart plots them in order).
    assert [item["label"] for item in stats["by_month"]] == ["2026-01", "2026-02"]

    january = _bucket(stats["by_month"], "2026-01")
    assert january["amount"] == "300.00"
    assert january["count"] == 2
    assert january["unconverted_count"] == 0
    february = _bucket(stats["by_month"], "2026-02")
    assert february["amount"] == "50.00"
    assert february["unconverted_count"] == 1

    year = _bucket(stats["by_year"], "2026")
    assert year["amount"] == "350.00"
    assert year["unconverted_count"] == 1

    currency = {item["currency"]: item for item in stats["by_currency"]}
    assert currency["CNY"]["amount"] == "350.00"
    assert currency["CNY"]["converted_amount"] == "350.00"
    assert currency["USD"]["amount"] == "100.00"
    assert currency["USD"]["converted_amount"] is None

    assert len(stats["unconverted"]) == 1
    assert stats["unconverted"][0]["currency"] == "USD"
    assert stats["unconverted"][0]["amount"] == "100.00"

    trip_bucket = _bucket(stats["by_trip"], trip)
    assert trip_bucket["name"] == "Beijing 2026"
    assert trip_bucket["amount"] == "350.00"
    assert trip_bucket["count"] == 3


def test_expense_statistics_counts_matching_conversion(client):
    """A converted expense joins the report total through its conversion pair."""
    headers = _headers(client, "stats_conversion")
    _expense(
        client,
        headers,
        category="entertainment",
        amount="50.00",
        currency="USD",
        converted_amount="360.00",
        converted_currency="CNY",
        exchange_rate="7.20",
        occurred_at="2026-03-01T02:30:00Z",
    )

    stats = _stats(client, headers)
    assert stats["total"] == "360.00"
    assert stats["converted_count"] == 1
    assert stats["unconverted_count"] == 0
    assert stats["average"] == "360.00"
    assert stats["by_currency"][0]["currency"] == "USD"
    assert stats["by_currency"][0]["converted_amount"] == "360.00"


def test_expense_statistics_without_timestamp():
    """Undated spend still lands in totals and categories, just not in time.

    Built directly on the aggregate so the missing ``occurred_at`` survives:
    the create API would stamp "now" on it.
    """
    from decimal import Decimal

    from app.models.expense import Expense
    from app.services.expense import build_expense_statistics

    undated = Expense(
        user_id=uuid.uuid4(), category="other", amount=Decimal("80.00"), currency="CNY"
    )
    dated = Expense(
        user_id=uuid.uuid4(),
        category="food",
        amount=Decimal("20.00"),
        currency="CNY",
        occurred_at=datetime(2026, 5, 1, 2, 30, tzinfo=UTC),
    )

    stats = build_expense_statistics([undated, dated], "CNY")
    assert stats.total == Decimal("100.00")
    assert stats.by_month == [
        ExpenseBreakdownItem(label="2026-05", amount=Decimal("20.00"), count=1)
    ]
    assert [item.label for item in stats.by_year] == ["2026"]
    assert _bucket_model(stats.by_category, "other").amount == Decimal("80.00")
    assert _bucket_model(stats.by_category, "food").amount == Decimal("20.00")


def test_expense_statistics_top_trips_are_ranked_and_capped(client):
    headers = _headers(client, "stats_top_trips")
    trip_ids = [_trip(client, headers, f"Trip {index}") for index in range(10)]
    for index, trip in enumerate(trip_ids):
        _expense(client, headers, amount=f"{(index + 1) * 100}.00", trip_id=trip)

    stats = _stats(client, headers)
    assert len(stats["by_trip"]) == 8
    amounts = [float(item["amount"]) for item in stats["by_trip"]]
    assert amounts == sorted(amounts, reverse=True)
    assert amounts == [1000.0, 900.0, 800.0, 700.0, 600.0, 500.0, 400.0, 300.0]
    assert stats["by_trip"][0]["label"] == trip_ids[-1]
    assert stats["by_trip"][0]["name"] == "Trip 9"


def test_expense_statistics_empty(client):
    headers = _headers(client, "stats_spend_empty")
    stats = _stats(client, headers)
    assert stats["total"] == "0.00"
    assert stats["count"] == 0
    assert stats["by_category"] == []
    assert stats["by_trip"] == []

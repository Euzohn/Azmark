"""Tests for the AviationStack flight-data provider (spec #66)."""

import asyncio
from datetime import date

import httpx
import pytest

from app.providers.aviationstack import AviationStackProvider

SAMPLE_FLIGHT = {
    "flight_date": "2026-01-15",
    "flight_status": "scheduled",
    "departure": {
        "airport": "Hong Kong International Airport",
        "timezone": "Asia/Hong_Kong",
        "iata": "HKG",
        "icao": "VHHH",
        "terminal": "1",
        "gate": "48",
        "baggage": None,
        "delay": None,
        "scheduled": "2026-01-15T09:00:00+08:00",
        "estimated": "2026-01-15T09:00:00+08:00",
        "actual": None,
        "estimated_runway": None,
        "actual_runway": None,
    },
    "arrival": {
        "airport": "Singapore Changi",
        "timezone": "Asia/Singapore",
        "iata": "SIN",
        "icao": "WSSS",
        "terminal": "4",
        "gate": "B2",
        "baggage": "2",
        "delay": None,
        "scheduled": "2026-01-15T13:00:00+08:00",
        "estimated": "2026-01-15T13:00:00+08:00",
        "actual": None,
        "estimated_runway": None,
        "actual_runway": None,
    },
    "airline": {
        "name": "Cathay Pacific",
        "iata": "CX",
        "icao": "CPA",
    },
    "flight": {
        "number": "659",
        "iata": "CX659",
        "icao": "CPA659",
    },
    "aircraft": None,
    "live": None,
}

OTHER_DAY_FLIGHT = {
    **SAMPLE_FLIGHT,
    "flight_date": "2026-01-16",
    "departure": {**SAMPLE_FLIGHT["departure"], "scheduled": "2026-01-16T09:00:00+08:00"},
}


async def _lookup(handler, flight_number: str = "CX659", lookup_date=None):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AviationStackProvider("test-key", client=client)
        return await provider.lookup(
            flight_number, date=lookup_date or date(2026, 1, 15)
        )


def test_parses_flight_and_params():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [SAMPLE_FLIGHT]})

    result = asyncio.run(_lookup(handler))
    assert result is not None
    assert result.flight_number == "CX659"
    assert result.airline_code == "CX"
    assert result.airline_name == "Cathay Pacific"
    assert result.origin_iata == "HKG"
    assert result.destination_iata == "SIN"
    assert result.origin_name == "Hong Kong International Airport"
    assert result.destination_name == "Singapore Changi"
    assert result.departure_time.isoformat() == "2026-01-15T09:00:00+08:00"
    assert result.arrival_time.isoformat() == "2026-01-15T13:00:00+08:00"
    assert result.departure_terminal == "1"
    assert result.departure_gate == "48"
    assert result.arrival_terminal == "4"
    assert result.arrival_gate == "B2"
    assert result.baggage_belt == "2"
    assert result.departure_timezone == "Asia/Hong_Kong"
    assert result.arrival_timezone == "Asia/Singapore"
    assert result.status == "scheduled"
    assert result.provider == "aviationstack"
    assert captured["params"]["access_key"] == "test-key"
    assert captured["params"]["flight_iata"] == "CX659"
    assert "flight_date" not in captured["params"]


def test_date_filter_finds_exact_match():
    flights = [OTHER_DAY_FLIGHT, SAMPLE_FLIGHT, {**OTHER_DAY_FLIGHT, "flight_date": "2026-01-14"}]

    def handler(request):
        return httpx.Response(200, json={"data": flights})

    result = asyncio.run(_lookup(handler, lookup_date=date(2026, 1, 15)))
    assert result is not None
    assert result.departure_time.isoformat() == "2026-01-15T09:00:00+08:00"


def test_no_date_match_returns_first():
    def handler(request):
        return httpx.Response(200, json={"data": [OTHER_DAY_FLIGHT]})

    result = asyncio.run(_lookup(handler, lookup_date=date(2026, 1, 15)))
    assert result is not None
    assert result.departure_time.isoformat() == "2026-01-16T09:00:00+08:00"


def test_error_response_returns_none():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "function_access_restricted",
                    "message": "plan does not support this function",
                }
            },
        )

    result = asyncio.run(_lookup(handler))
    assert result is None


def test_empty_data_returns_none():
    result = asyncio.run(_lookup(lambda request: httpx.Response(200, json={"data": []})))
    assert result is None


def test_malformed_payload_returns_none():
    result = asyncio.run(_lookup(lambda request: httpx.Response(200, json={"weird": True})))
    assert result is None


def test_404_returns_none():
    handler = lambda request: httpx.Response(404, json={"error": "not found"})  # noqa: E731
    result = asyncio.run(_lookup(handler))
    assert result is None


def test_http_error_raises():
    async def main():
        with pytest.raises(httpx.HTTPError):
            await _lookup(lambda request: httpx.Response(500, json={"error": "oops"}))

    asyncio.run(main())


def test_no_api_key_returns_none():
    provider = AviationStackProvider("")
    result = asyncio.run(provider.lookup("CX659", date=date(2026, 1, 15)))
    assert result is None

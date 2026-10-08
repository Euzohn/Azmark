import asyncio
from datetime import date

import httpx
import pytest

from app.providers.aerodatabox import AeroDataBoxProvider

SAMPLE_FLIGHT = {
    "flights": [
        {
            "number": "659",
            "status": "scheduled",
            "flight": {"iata": "CX659", "icao": "CPA659", "number": "659"},
            "departure": {
                "airport": {
                    "iata": "HKG",
                    "icao": "VHHH",
                    "name": "Hong Kong International Airport",
                    "city": "Hong Kong",
                    "country": "China",
                },
                "time": "2026-10-09T09:00:00+08:00",
                "terminal": "1",
                "timezone": "Asia/Hong_Kong",
            },
            "arrival": {
                "airport": {
                    "iata": "SIN",
                    "icao": "WSSS",
                    "name": "Singapore Changi Airport",
                    "city": "Singapore",
                    "country": "Singapore",
                },
                "time": "2026-10-09T12:15:00+08:00",
                "terminal": "4",
                "timezone": "Asia/Singapore",
            },
            "aircraft": {
                "reg": "B-KPM",
                "modeS": "780A13",
                "model": {"code": "77W", "text": "Boeing 777-300ER"},
            },
            "airline": {"name": "Cathay Pacific", "iata": "CX", "icao": "CPA"},
        }
    ]
}


async def _lookup(handler, flight_number: str = "CX659"):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AeroDataBoxProvider("test-key", client=client)
        return await provider.lookup(flight_number, date=date(2026, 10, 9))


def test_parses_flight_and_headers():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        return httpx.Response(200, json=SAMPLE_FLIGHT)

    result = asyncio.run(_lookup(handler))
    assert result is not None
    assert result.flight_number == "CX659"
    assert result.airline_code == "CX"
    assert result.airline_name == "Cathay Pacific"
    assert result.origin_iata == "HKG"
    assert result.destination_iata == "SIN"
    assert result.origin_name == "Hong Kong International Airport"
    assert result.destination_name == "Singapore Changi Airport"
    assert result.departure_time.isoformat() == "2026-10-09T09:00:00+08:00"
    assert result.arrival_time.isoformat() == "2026-10-09T12:15:00+08:00"
    assert result.aircraft == "Boeing 777-300ER"
    assert result.status == "scheduled"
    assert result.provider == "aerodatabox"
    assert "/flights/number/CX659/2026-10-09" in captured["url"]
    assert captured["headers"]["X-RapidAPI-Key"] == "test-key"
    assert captured["headers"]["X-RapidAPI-Host"] == "aerodatabox.p.rapidapi.com"


def test_404_returns_none():
    handler = lambda request: httpx.Response(404, json={"message": "not found"})  # noqa: E731
    result = asyncio.run(_lookup(handler))
    assert result is None


def test_empty_flights_returns_none():
    result = asyncio.run(_lookup(lambda request: httpx.Response(200, json={"flights": []})))
    assert result is None


def test_malformed_payload_returns_none():
    result = asyncio.run(_lookup(lambda request: httpx.Response(200, json={"weird": True})))
    assert result is None


def test_http_error_raises():
    async def main():
        with pytest.raises(httpx.HTTPError):
            await _lookup(lambda request: httpx.Response(500, json={"message": "oops"}))

    asyncio.run(main())

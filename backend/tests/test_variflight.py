"""Tests for the VariFlight (飞常准) Aviation MCP provider (spec #66)."""

import asyncio
import json
from datetime import date

import httpx

from app.providers.variflight import VariflightProvider

SAMPLE_FLIGHT = {
    "FlightNo": "MU2157",
    "FlightCompany": "中国东方航空",
    "FlightCompanyEn": "China Eastern Airlines",
    "FlightDepcode": "PEK",
    "FlightArrcode": "SHA",
    "FlightDepAirport": "北京首都国际机场",
    "FlightArrAirport": "上海虹桥国际机场",
    "FlightHTerminal": "T2",
    "FlightTerminal": "T2",
    "BoardGate": "C12",
    "FlightDeptimePlanDate": "2026-03-20 08:00",
    "FlightArrtimePlanDate": "2026-03-20 10:20",
    "FlightDeptimeReadyDate": "2026-03-20 08:10",
    "FlightArrtimeReadyDate": "2026-03-20 10:25",
    "FlightDeptimeDate": "2026-03-20 08:12",
    "FlightArrtimeDate": "",
    "FlightState": "起飞",
    "ftype": "A320",
    "FlightDistance": "1080",
    "BaggageCarousel": "23",
    "CheckinCounter": "H01-H12",
    "AircraftReg": "B-1234",
}


def _envelope(flight: dict | None) -> dict:
    text = json.dumps({"code": 200, "data": [flight] if flight else []})
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": text}]},
    }


async def _lookup(handler, flight_number: str = "MU2157"):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = VariflightProvider("test-key", client=client)
        return await provider.lookup(flight_number, date=date(2026, 3, 20))


def test_parses_mcp_flight_and_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_envelope(SAMPLE_FLIGHT))

    result = asyncio.run(_lookup(handler))
    assert result is not None
    assert result.flight_number == "MU2157"
    assert result.airline_code == "MU"
    assert result.airline_name == "China Eastern Airlines"
    assert result.origin_iata == "PEK"
    assert result.destination_iata == "SHA"
    assert result.origin_name == "北京首都国际机场"
    assert result.departure_time.isoformat() == "2026-03-20T08:00:00"
    assert result.arrival_time.isoformat() == "2026-03-20T10:20:00"
    assert result.actual_departure_time.isoformat() == "2026-03-20T08:12:00"
    assert result.actual_arrival_time.isoformat() == "2026-03-20T10:25:00"
    assert result.departure_terminal == "T2"
    assert result.arrival_terminal == "T2"
    assert result.departure_gate == "C12"
    assert result.check_in_desk == "H01-H12"
    assert result.baggage_belt == "23"
    assert result.aircraft_model == "A320"
    assert result.aircraft_reg == "B-1234"
    assert result.status == "scheduled"
    assert result.distance == 1080.0
    assert result.provider == "variflight"

    assert captured["headers"]["x-api-key"] == "test-key"
    body = captured["body"]
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "searchFlightsByNumber"
    assert body["params"]["arguments"] == {"fnum": "MU2157", "date": "2026-03-20"}


def test_parses_sse_response_and_selects_requested_number():
    other = {**SAMPLE_FLIGHT, "FlightNo": "MU9999"}
    payload = _envelope(other)
    payload["result"]["content"][0]["text"] = json.dumps({"data": [other, SAMPLE_FLIGHT]})
    body = f"event: message\ndata: {json.dumps(payload)}\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    result = asyncio.run(_lookup(handler))
    assert result is not None
    assert result.flight_number == "MU2157"


def test_empty_result_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(None))

    assert asyncio.run(_lookup(handler)) is None


def test_tool_error_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "Error executing tool"}],
                },
            },
        )

    assert asyncio.run(_lookup(handler)) is None


def test_maps_cancelled_and_completed_states():
    from app.providers.variflight import _map_status

    assert _map_status("取消") == "cancelled"
    assert _map_status("Cancelled") == "cancelled"
    assert _map_status("到达") == "completed"
    assert _map_status("计划") == "scheduled"
    assert _map_status("起飞") == "scheduled"
    assert _map_status(None) is None

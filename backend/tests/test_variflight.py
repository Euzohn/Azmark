"""Tests for the VariFlight (飞常准) Aviation MCP provider (spec #66)."""

import asyncio
import json
from datetime import date

import httpx

from app.providers.variflight import VariflightProvider, _tz_string

# Mirrors a real searchFlightsByNumber response (SHA -> PEK, MU5101).
SAMPLE_FLIGHT = {
    "FlightNo": "MU5101",
    "FlightCompany": "中国东方航空股份有限公司",
    "FlightDepcode": "SHA",
    "FlightArrcode": "PEK",
    "FlightDepAirport": "上海虹桥",
    "FlightArrAirport": "北京首都",
    "AircraftNumber": "B7881",
    "FlightDeptimePlanDate": "2026-10-20 08:00:00",
    "FlightArrtimePlanDate": "2026-10-20 10:10:00",
    "FlightDeptimeReadyDate": "",
    "FlightArrtimeReadyDate": "2026-10-20 10:07:29",
    "FlightDeptimeDate": "2026-10-20 08:18:29",
    "FlightArrtimeDate": "2026-10-20 10:02:00",
    "CheckinTable": "C03-D07",
    "BoardGate": "56",
    "BaggageID": "13",
    "FlightState": "到达",
    "FlightHTerminal": "T2",
    "FlightTerminal": "T2",
    "ftype": "B77W",
    "generic": "Boeing 777-39P",
    "distance": "1178",
    "org_timezone": "28800",
    "dst_timezone": "28800",
    "StopFlag": "0",
    "alternate_info": [],
    "FillFlightInfo": None,
}


def _envelope_text(flight: dict | None, *, as_repr: bool = False) -> str:
    payload = {"code": 200, "data": [flight] if flight else []}
    if as_repr:
        # This is the real shape VariFlight returns: Python repr, single quotes,
        # prefixed with "Flight details: ".
        return f"Flight details: {payload!r}"
    return json.dumps(payload)


def _envelope(flight: dict | None, *, as_repr: bool = False) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": _envelope_text(flight, as_repr=as_repr)}]},
    }


async def _lookup(handler, flight_number: str = "MU5101"):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = VariflightProvider("test-key", client=client)
        return await provider.lookup(flight_number, date=date(2026, 3, 20))


def _assert_flight(result):
    assert result is not None
    assert result.flight_number == "MU5101"
    assert result.airline_code == "MU"
    # Chinese-only company name is dropped so the en-US UI keeps the English
    # reference name; the local airline lookup fills it in.
    assert result.airline_name is None
    assert result.origin_iata == "SHA"
    assert result.destination_iata == "PEK"
    assert result.origin_name is None
    assert result.destination_name is None
    assert result.departure_time.isoformat() == "2026-10-20T08:00:00+08:00"
    assert result.arrival_time.isoformat() == "2026-10-20T10:10:00+08:00"
    assert result.actual_departure_time.isoformat() == "2026-10-20T08:18:29+08:00"
    assert result.actual_arrival_time.isoformat() == "2026-10-20T10:02:00+08:00"
    assert result.departure_timezone == "+08:00"
    assert result.arrival_timezone == "+08:00"
    assert result.departure_terminal == "T2"
    assert result.arrival_terminal == "T2"
    assert result.departure_gate == "56"
    assert result.check_in_desk == "C03-D07"
    assert result.baggage_belt == "13"
    assert result.aircraft_model == "Boeing 777-39P"
    assert result.aircraft_reg == "B7881"
    assert result.status == "completed"
    assert result.distance == 1178.0
    assert result.provider == "variflight"


def test_parses_json_envelope_and_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_envelope(SAMPLE_FLIGHT))

    result = asyncio.run(_lookup(handler))
    _assert_flight(result)

    assert captured["headers"]["x-api-key"] == "test-key"
    body = captured["body"]
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "searchFlightsByNumber"
    assert body["params"]["arguments"] == {"fnum": "MU5101", "date": "2026-03-20"}


def test_parses_python_repr_envelope():
    # VariFlight actually returns a Python repr() dict, not JSON.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(SAMPLE_FLIGHT, as_repr=True))

    result = asyncio.run(_lookup(handler))
    _assert_flight(result)


def test_sse_repr_response_selects_requested_number():
    # VariFlight actually returns a Python repr() dict, not JSON.
    other = {**SAMPLE_FLIGHT, "FlightNo": "MU9999"}
    both = {"code": 200, "data": [other, SAMPLE_FLIGHT]}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": f"Flight details: {both!r}"}],
        },
    }
    body = f"event: message\ndata: {json.dumps(payload)}\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    result = asyncio.run(_lookup(handler))
    _assert_flight(result)


def test_empty_result_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(None, as_repr=True))

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


def test_maps_states_and_timezone():
    from app.providers.variflight import _map_status

    assert _map_status("到达") == "completed"
    assert _map_status("起飞") == "scheduled"
    assert _map_status("取消") == "cancelled"
    assert _map_status("计划") == "scheduled"
    assert _map_status(None) is None
    assert _tz_string("28800") == "+08:00"
    assert _tz_string("-18000") == "-05:00"
    assert _tz_string(None) is None

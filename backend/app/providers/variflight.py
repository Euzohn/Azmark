"""VariFlight (飞常准) flight provider — Aviation MCP (spec #66).

Docs: https://ai.variflight.com/zh/docs/aviation

The MCP server is stateless JSON-RPC over HTTP. We call the
``searchFlightsByNumber`` tool and parse the JSON it returns in a text content
block. VariFlight uses PascalCase fields such as ``FlightDeptimePlanDate``
(scheduled) and ``FlightDeptimeDate`` (actual); the parser accepts common
aliases because the upstream field set varies by route.

The API key is sent only to this provider and never logged (spec #45/#96).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from logging import getLogger
from typing import Any

import httpx

from app.core.config import settings
from app.providers.base import FlightLookupResult, FlightProvider

logger = getLogger(__name__)


def _pick(item: dict[str, Any], *keys: str) -> Any:
    """Case-insensitive first non-empty value for any of the aliases."""
    lowered = {str(key).lower(): value for key, value in item.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, "", []):
            return value
    return None


def _as_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value).strip() or None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse VariFlight local wall-clock strings — no timezone is attached."""
    text = _as_str(value)
    if not text:
        return None
    text = text.replace("/", "-")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _parse_distance(value: Any) -> float | None:
    text = _as_str(value)
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else None


def _map_status(value: Any) -> str | None:
    """Map VariFlight's Chinese/English state to our scheduled/completed/cancelled."""
    text = _as_str(value)
    if not text:
        return None
    lowered = text.lower()
    if any(token in text for token in ("取消",)) or any(
        token in lowered for token in ("cancel", "cancelled", "canceled")
    ):
        return "cancelled"
    if any(token in text for token in ("到达", "落地", "结束", "完成")) or any(
        token in lowered for token in ("arrived", "landed", "completed")
    ):
        return "completed"
    if any(
        token in text for token in ("计划", "预计", "延误", "起飞", "备降", "返航", "登机")
    ) or any(token in lowered for token in ("scheduled", "delayed", "departed", "boarding")):
        return "scheduled"
    return None


def _mcp_payload(response: httpx.Response) -> dict[str, Any] | None:
    """Decode a JSON or text/event-stream JSON-RPC response."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if not data or data == "[DONE]":
                continue
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                continue
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _tool_json(payload: dict[str, Any] | None) -> Any:
    """Extract and decode the JSON text returned by the MCP tool."""
    if not isinstance(payload, dict):
        return None
    if payload.get("error"):
        logger.warning("VariFlight: MCP error: %s", str(payload["error"])[:300])
        return None
    result = payload.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        if isinstance(result, dict):
            logger.info("VariFlight: tool error: %s", str(result.get("content"))[:300])
        return None
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if not isinstance(text, str):
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.warning("VariFlight: non-JSON tool output: %s", text[:300])
                return None
    return None


def _flight_list(data: Any) -> list[dict[str, Any]]:
    """Normalize {data: [...]}, {data: {...}}, {flights: [...]} or a bare list."""
    items = data.get("data") if isinstance(data, dict) else data
    if isinstance(items, dict):
        for key in ("flights", "list", "items", "data"):
            nested = items.get(key)
            if isinstance(nested, list):
                items = nested
                break
        else:
            items = [items]
    if not isinstance(items, list):
        return []
    flights: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, list):
            flights.extend(entry for entry in item if isinstance(entry, dict))
        elif isinstance(item, dict):
            flights.append(item)
    return flights


class VariflightProvider(FlightProvider):
    name = "variflight"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or settings.variflight_mcp_url).rstrip("/")
        self._client = client

    async def lookup(self, flight_number: str, *, date: date) -> FlightLookupResult | None:
        if not self.api_key:
            return None
        number = flight_number.replace(" ", "").upper()
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "searchFlightsByNumber",
                "arguments": {"fnum": number, "date": f"{date:%Y-%m-%d}"},
            },
        }
        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json, text/event-stream",
        }
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(20.0))
        try:
            response = await client.post(self.base_url, json=body, headers=headers)
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code == 404:
            logger.info("VariFlight: no flight for %s on %s (404)", number, date)
            return None
        response.raise_for_status()
        logger.info("VariFlight: status=%s for %s", response.status_code, number)

        flights = _flight_list(_tool_json(_mcp_payload(response)))
        if not flights:
            return None
        flight = next(
            (
                item
                for item in flights
                if str(_pick(item, "FlightNo", "FlightNumber", "fnum") or "")
                .replace(" ", "")
                .upper()
                == number
            ),
            flights[0],
        )
        return self._parse(flight, number)

    def _parse(self, flight: dict[str, Any], flight_number: str) -> FlightLookupResult:
        airline_name = _as_str(
            _pick(flight, "FlightCompanyEn", "AirlineNameEn", "CompanyEn", "AirlineEn")
        )
        if not airline_name:
            company = _as_str(_pick(flight, "FlightCompany", "AirlineName", "Company"))
            # VariFlight's Chinese company names would override the English
            # reference name used by the en-US UI; keep ASCII values only.
            if company and company.isascii():
                airline_name = company
        airline_code = _as_str(_pick(flight, "FlightCompanyCode", "AirlineCode", "CarrierCode"))
        if not airline_code:
            match = re.match(r"^([A-Z0-9]{2})\d", flight_number)
            if match:
                airline_code = match.group(1)

        return FlightLookupResult(
            flight_number=flight_number,
            airline_code=airline_code,
            airline_name=airline_name,
            origin_iata=_as_str(
                _pick(flight, "FlightDepcode", "DepAirportCode", "DepCode", "OriginCode")
            ),
            destination_iata=_as_str(
                _pick(flight, "FlightArrcode", "ArrAirportCode", "ArrCode", "DestCode")
            ),
            origin_name=_as_str(_pick(flight, "FlightDepAirport", "DepAirport", "DepAirportName")),
            destination_name=_as_str(
                _pick(flight, "FlightArrAirport", "ArrAirport", "ArrAirportName")
            ),
            departure_time=_parse_datetime(
                _pick(flight, "FlightDeptimePlanDate", "FlightDeptimePlan", "DepTimePlan")
            ),
            arrival_time=_parse_datetime(
                _pick(flight, "FlightArrtimePlanDate", "FlightArrtimePlan", "ArrTimePlan")
            ),
            actual_departure_time=_parse_datetime(
                _pick(
                    flight,
                    "FlightDeptimeDate",
                    "FlightDeptimeActual",
                    "DepTimeActual",
                    "FlightDeptimeReadyDate",
                )
            ),
            actual_arrival_time=_parse_datetime(
                _pick(
                    flight,
                    "FlightArrtimeDate",
                    "FlightArrtimeActual",
                    "ArrTimeActual",
                    "FlightArrtimeReadyDate",
                )
            ),
            departure_terminal=_as_str(
                _pick(flight, "FlightHTerminal", "FlightDepTerminal", "DepTerminal")
            ),
            departure_gate=_as_str(_pick(flight, "BoardGate", "FlightDepGate", "DepGate", "Gate")),
            arrival_terminal=_as_str(
                _pick(flight, "FlightTerminal", "FlightArrTerminal", "ArrTerminal")
            ),
            arrival_gate=_as_str(_pick(flight, "FlightArrGate", "ArrGate", "ArrivalGate")),
            check_in_desk=_as_str(
                _pick(
                    flight,
                    "CheckinCounter",
                    "CheckInDesk",
                    "CheckinDesk",
                    "CheckinCounterNo",
                )
            ),
            baggage_belt=_as_str(
                _pick(
                    flight,
                    "BaggageCarousel",
                    "BaggageReclaim",
                    "BaggageBelt",
                    "ArrBaggage",
                    "LuggageCarousel",
                )
            ),
            aircraft_model=_as_str(
                _pick(
                    flight,
                    "ftype",
                    "FlightType",
                    "AircraftType",
                    "AircraftModel",
                    "PlaneType",
                )
            ),
            aircraft_reg=_as_str(
                _pick(flight, "AircraftReg", "FlightReg", "RegisterNo", "ACReg", "TailNo")
            ),
            status=_map_status(_pick(flight, "FlightState", "FlightStatus", "State", "Status")),
            distance=_parse_distance(_pick(flight, "FlightDistance", "Distance", "DistanceKm")),
            provider=self.name,
        )

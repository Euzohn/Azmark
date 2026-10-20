"""VariFlight (飞常准) flight provider — Aviation MCP (spec #66).

Docs: https://ai.variflight.com/zh/docs/aviation

The MCP server is stateless JSON-RPC over HTTP. We call the
``searchFlightsByNumber`` tool and parse the payload it returns in a text
content block. Important: the tool wraps its result as a Python ``repr()``
dict (single quotes, ``Flight details: { ... }``), not JSON, so the parser
tries ``json.loads`` first and falls back to ``ast.literal_eval``.

VariFlight field reference (confirmed against a live response):
  FlightNo / FlightCompany          flight number / airline (Chinese)
  FlightDepcode / FlightArrcode     IATA airport codes
  FlightDepAirport / FlightArrAirport  airport names (Chinese, short)
  FlightDeptimePlanDate / FlightArrtimePlanDate  scheduled times (local)
  FlightDeptimeDate     / FlightArrtimeDate       actual times (local)
  FlightDeptimeReadyDate/ FlightArrtimeReadyDate  estimated times (local)
  FlightHTerminal / FlightTerminal  departure / arrival terminal
  BoardGate                          boarding (departure) gate
  CheckinTable                       check-in counters (e.g. "C03-D07")
  BaggageID                          baggage belt (e.g. "13")
  ftype / generic / AircraftNumber   IATA type / full model / tail reg
  FlightState                        Chinese status (到达/起飞/取消/计划…)
  distance                           km (lowercase)
  org_timezone / dst_timezone        UTC offset in seconds (e.g. 28800)

The API key is sent only to this provider and never logged (spec #45/#96).
Web snippets are treated as untrusted data (spec #70): we parse them as
literals only, never executing anything.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import date, datetime, timedelta, timezone
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


def _parse_datetime(value: Any, *, offset_seconds: Any = None) -> datetime | None:
    """Parse VariFlight local wall-clock strings.

    When ``offset_seconds`` is supplied (VariFlight ships UTC offsets in
    seconds, e.g. 28800 for +08:00) the returned datetime is made aware so
    downstream code can convert to the viewer's timezone.
    """
    text = _as_str(value)
    if not text:
        return None
    text = text.replace("/", "-")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    secs = _as_int(offset_seconds)
    if secs is not None:
        try:
            return parsed.replace(tzinfo=timezone(timedelta(seconds=secs)))
        except (OverflowError, ValueError):
            return parsed
    return parsed


def _as_int(value: Any) -> int | None:
    text = _as_str(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _tz_string(offset_seconds: Any) -> str | None:
    """28800 -> "+08:00". Used for the departure/arrival_timezone fields."""
    secs = _as_int(offset_seconds)
    if secs is None:
        return None
    sign = "+" if secs >= 0 else "-"
    secs = abs(secs)
    return f"{sign}{secs // 3600:02d}:{(secs % 3600) // 60:02d}"


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
    if "取消" in text or any(token in lowered for token in ("cancel", "cancelled", "canceled")):
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


def _literal_payload(text: str) -> Any:
    """Parse the tool's text content.

    VariFlight returns a Python ``repr()`` dict (single quotes) prefixed with
    "Flight details: ". Some deployments may return plain JSON, so try JSON
    first, then fall back to ``ast.literal_eval`` on the dict substring.
    ``ast.literal_eval`` only evaluates literal expressions — it never runs
    code, so untrusted snippets stay data (spec #70).
    """
    if not isinstance(text, str) or not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return ast.literal_eval(text[start : end + 1])
    except (ValueError, SyntaxError):
        logger.warning("VariFlight: unparseable tool output: %s", text[:300])
        return None


def _tool_json(payload: dict[str, Any] | None) -> Any:
    """Extract and decode the payload returned by the MCP tool."""
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
            return _literal_payload(block.get("text"))
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
        org_tz_secs = _pick(flight, "org_timezone", "OrgTimezone", "dep_timezone")
        dst_tz_secs = _pick(flight, "dst_timezone", "DstTimezone", "arr_timezone")

        airline_name = _as_str(
            _pick(flight, "FlightCompanyEn", "AirlineNameEn", "CompanyEn", "AirlineEn")
        )
        if not airline_name:
            company = _as_str(_pick(flight, "FlightCompany", "AirlineName", "Company"))
            # VariFlight's Chinese company name would override the English
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
            # Airport names come back Chinese-only; leave them to the local
            # reference so en-US does not show Chinese strings.
            origin_name=None,
            destination_name=None,
            departure_time=_parse_datetime(
                _pick(flight, "FlightDeptimePlanDate", "FlightDeptimePlan", "DepTimePlan"),
                offset_seconds=org_tz_secs,
            ),
            arrival_time=_parse_datetime(
                _pick(flight, "FlightArrtimePlanDate", "FlightArrtimePlan", "ArrTimePlan"),
                offset_seconds=dst_tz_secs,
            ),
            actual_departure_time=_parse_datetime(
                _pick(
                    flight,
                    "FlightDeptimeDate",
                    "FlightDeptimeActual",
                    "DepTimeActual",
                    "FlightDeptimeReadyDate",
                ),
                offset_seconds=org_tz_secs,
            ),
            actual_arrival_time=_parse_datetime(
                _pick(
                    flight,
                    "FlightArrtimeDate",
                    "FlightArrtimeActual",
                    "ArrTimeActual",
                    "FlightArrtimeReadyDate",
                ),
                offset_seconds=dst_tz_secs,
            ),
            departure_timezone=_tz_string(org_tz_secs),
            arrival_timezone=_tz_string(dst_tz_secs),
            departure_terminal=_as_str(
                _pick(flight, "FlightHTerminal", "FlightDepTerminal", "DepTerminal")
            ),
            departure_gate=_as_str(_pick(flight, "BoardGate", "FlightDepGate", "DepGate", "Gate")),
            arrival_terminal=_as_str(
                _pick(flight, "FlightTerminal", "FlightArrTerminal", "ArrTerminal")
            ),
            arrival_gate=_as_str(_pick(flight, "FlightArrGate", "ArrGate", "ArrivalGate")),
            check_in_desk=_as_str(
                _pick(flight, "CheckinTable", "CheckinCounter", "CheckInDesk", "CheckinDesk")
            ),
            baggage_belt=_as_str(
                _pick(
                    flight,
                    "BaggageID",
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
                    "generic",
                    "AircraftModel",
                    "PlaneType",
                    "ftype",
                    "FlightType",
                    "AircraftType",
                )
            ),
            aircraft_reg=_as_str(
                _pick(
                    flight,
                    "AircraftNumber",
                    "AircraftReg",
                    "FlightReg",
                    "RegisterNo",
                    "ACReg",
                    "TailNo",
                )
            ),
            status=_map_status(_pick(flight, "FlightState", "FlightStatus", "State", "Status")),
            distance=_parse_distance(
                _pick(flight, "distance", "FlightDistance", "Distance", "DistanceKm")
            ),
            provider=self.name,
        )

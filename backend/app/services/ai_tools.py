"""AI tool registry (spec #31, #32, #33).

All tools are bound to the current user (spec #34). READ tools execute
immediately and feed results back into the conversation. WRITE and DESTRUCTIVE
tools never execute — they become ``AiProposal`` objects returned to the
frontend for explicit user confirmation (spec #69, #93).
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.orm import Session

from app.schemas.ai import AiProposal
from app.services import reference
from app.services.dashboard import DashboardService

logger = logging.getLogger(__name__)


class ToolPermission(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


def _compact_record(record) -> dict:
    """Serialize a record for the LLM — never includes sensitive fields (#45/#96)."""
    return {
        "id": str(record.id),
        "type": record.type,
        "origin": record.origin,
        "destination": record.destination,
        "service_number": record.service_number,
        "carrier": record.carrier,
        "airline_code": record.airline_code,
        "departure_time": record.departure_time.isoformat() if record.departure_time else None,
        "arrival_time": record.arrival_time.isoformat() if record.arrival_time else None,
        "status": record.status,
        "distance_km": float(record.distance) if record.distance else None,
        "cabin_class": record.cabin_class,
        "seat": record.seat,
        "departure_terminal": record.departure_terminal,
        "departure_gate": record.departure_gate,
        "arrival_terminal": record.arrival_terminal,
        "arrival_gate": record.arrival_gate,
        "aircraft_model": record.aircraft_model,
        "train_type": record.train_type,
        "carriage": record.carriage,
        "seat_type": record.seat_type,
        "price": float(record.price) if record.price is not None else None,
        "currency": record.currency,
    }


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    permission: ToolPermission
    read: Callable[[Session, uuid.UUID, dict], Awaitable[dict]] | None = None
    proposal: Callable[[dict], AiProposal] | None = None


async def _search_records(db: Session, user_id: uuid.UUID, args: dict) -> dict:
    from app.repositories.transport import TransportRepository

    query = args.get("query", "")
    record_type = args.get("record_type")
    limit = min(int(args.get("limit", 20)), 50)
    repo = TransportRepository(db)
    records = repo.search(user_id=user_id, query=query, record_type=record_type, limit=limit)
    return {"count": len(records), "items": [_compact_record(r) for r in records]}


async def _get_statistics(db: Session, user_id: uuid.UUID, _args: dict) -> dict:
    service = DashboardService(db)
    stats = service.overview(user_id=user_id)
    breakdown = service.statistics(user_id=user_id)
    return {
        "totals": {
            "countries": stats.stats.countries,
            "cities": stats.stats.cities,
            "journeys": stats.stats.journeys,
            "distance_km": stats.stats.distance_km,
            "flights": stats.stats.flights,
            "trains": stats.stats.trains,
            "transports": stats.stats.transports,
            "trips": stats.stats.trips,
        },
        "by_month": [item.model_dump() for item in breakdown.by_month],
        "by_airline": [item.model_dump() for item in breakdown.by_airline],
        "by_airport": [item.model_dump() for item in breakdown.by_airport],
    }


async def _get_record(db: Session, user_id: uuid.UUID, args: dict) -> dict:
    from app.repositories.transport import TransportRepository

    record_id = args.get("record_id") or args.get("id")
    if not record_id:
        return {"error": "record_id is required"}
    try:
        parsed_id = uuid.UUID(str(record_id))
    except (ValueError, TypeError):
        return {"error": "invalid record id"}
    repo = TransportRepository(db)
    record = repo.get(user_id=user_id, record_id=parsed_id)
    if record is None:
        return {"error": "record not found"}
    compact = _compact_record(record)
    compact["notes"] = record.notes
    return compact


async def _lookup_flight(db: Session, user_id: uuid.UUID, args: dict) -> dict:
    """Look up flight info by number + date via external providers (spec #31, #66).

    AeroDataBox is tried first (more accurate for most routes). Only if it
    returns no result do we fall back to other providers like AviationStack,
    whose data may be less reliable.
    """
    from app.services.flight_enrichment import FlightEnrichmentService

    flight_number = (args.get("flight_number") or "").strip()
    if not flight_number:
        return {"error": "flight_number is required"}
    flight_date_str = args.get("date")
    if flight_date_str:
        try:
            from datetime import date as date_type

            flight_date = date_type.fromisoformat(str(flight_date_str))
        except ValueError:
            return {"error": "invalid date format, use YYYY-MM-DD"}
    else:
        from datetime import date as date_type

        flight_date = date_type.today()

    service = FlightEnrichmentService(db)
    try:
        # Try AeroDataBox first — it is the preferred, more accurate source.
        result = await service.lookup(
            user_id=user_id,
            flight_number=flight_number,
            date=flight_date,
            provider="aerodatabox",
        )
        # If AeroDataBox had no data (source == "local"), try other providers.
        if result.source == "local":
            result = await service.lookup(
                user_id=user_id,
                flight_number=flight_number,
                date=flight_date,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI tool lookup_flight raised: %r", exc)
        return {"error": "flight lookup failed"}

    if result.source == "local":
        return {
            "flight_number": result.flight_number,
            "airline_code": result.airline_code,
            "airline_name": result.airline_name,
            "source": "local",
            "hint": (
                "No external provider configured. Route/times are not available. "
                "Ask the user for origin, destination, and departure time, or "
                "configure a flight data provider in Settings → Provider Keys."
            ),
        }
    response = {
        "flight_number": result.flight_number,
        "airline_code": result.airline_code,
        "airline_name": result.airline_name,
        "airline_name_zh": result.airline_name_zh,
        "origin_iata": result.origin_iata,
        "destination_iata": result.destination_iata,
        "origin_name": result.origin_name,
        "destination_name": result.destination_name,
        "departure_time": result.departure_time.isoformat() if result.departure_time else None,
        "arrival_time": result.arrival_time.isoformat() if result.arrival_time else None,
        "actual_departure_time": (
            result.actual_departure_time.isoformat() if result.actual_departure_time else None
        ),
        "actual_arrival_time": (
            result.actual_arrival_time.isoformat() if result.actual_arrival_time else None
        ),
        "departure_terminal": result.departure_terminal,
        "departure_gate": result.departure_gate,
        "arrival_terminal": result.arrival_terminal,
        "arrival_gate": result.arrival_gate,
        "check_in_desk": result.check_in_desk,
        "baggage_belt": result.baggage_belt,
        "aircraft_model": result.aircraft_model,
        "aircraft_reg": result.aircraft_reg,
        "departure_timezone": result.departure_timezone,
        "arrival_timezone": result.arrival_timezone,
        "status": result.status,
        "distance_km": result.distance,
        "aircraft": result.aircraft,
        "source": result.source,
    }
    if result.source == "aviationstack":
        response["hint"] = (
            "Data from AviationStack (AeroDataBox had no result). "
            "Times or airports may be less accurate — verify with the user."
        )
    return response


# Chinese train-number prefixes → category. Used as a server-side safety net so
# train_type is filled even if the LLM omits it (spec #13).
_TRAIN_TYPE_BY_PREFIX: dict[str, str] = {
    "G": "高铁",
    "D": "动车",
    "C": "城际",
    "Z": "直达特快",
    "T": "特快",
    "K": "快速",
    "L": "临时",
    "Y": "旅游",
}


def _parse_dt(value: object) -> datetime | None:
    """Parse an ISO 8601 string defensively; naive values are treated as UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _infer_status(data: dict) -> str | None:
    """Infer scheduled/completed from the times relative to now."""
    anchor = _parse_dt(data.get("arrival_time")) or _parse_dt(data.get("departure_time"))
    if anchor is None:
        return None
    return "completed" if anchor < datetime.now(UTC) else "scheduled"


def _fill_inferred_fields(record_type: str, data: object) -> dict:
    """Server-side safety net for fields the LLM may have omitted.

    Only fills missing values — never overrides what the LLM provided.
    """
    if not isinstance(data, dict):
        return {}
    data = dict(data)

    if not data.get("status"):
        status = _infer_status(data)
        if status:
            data["status"] = status

    service = str(data.get("service_number") or "").strip().upper()
    if record_type == "flight":
        if service and not data.get("airline_code"):
            match = re.match(r"^([A-Z0-9]{2})\d", service)
            if match:
                data["airline_code"] = match.group(1)
        airline_code = str(data.get("airline_code") or "").strip().upper()
        if airline_code and not data.get("carrier"):
            airline = reference.get_airline_by_iata(airline_code)
            if airline:
                data["carrier"] = airline.get("name")
    elif record_type == "train":
        if service and not data.get("train_type"):
            train_type = _TRAIN_TYPE_BY_PREFIX.get(service[0])
            if train_type:
                data["train_type"] = train_type

    return data


def _create_transport_proposal(args: dict) -> AiProposal:
    record_type = args.get("record_type") or args.get("type") or "other"
    data = _fill_inferred_fields(record_type, args.get("data", {}))
    summary_parts = [
        record_type,
        f"{data.get('origin', '—')} → {data.get('destination', '—')}",
    ]
    if data.get("service_number"):
        summary_parts.append(data["service_number"])
    if data.get("departure_time"):
        summary_parts.append(str(data["departure_time"]))
    return AiProposal(
        id=uuid.uuid4().hex,
        action="create_transport",
        record_type=record_type,
        summary=" · ".join(summary_parts),
        data=data,
    )


def _delete_transport_proposal(args: dict) -> AiProposal:
    record_type = args.get("record_type") or args.get("type") or "other"
    record_id = args.get("record_id") or args.get("id", "")
    return AiProposal(
        id=uuid.uuid4().hex,
        action="delete_transport",
        record_type=record_type,
        summary=f"Delete {record_type} {record_id}",
        data={"record_id": record_id},
    )


TOOLS: dict[str, ToolDef] = {
    "search_records": ToolDef(
        name="search_records",
        description=(
            "Search the user's transport records by keyword (city, flight/train "
            "number, airline, operator). Returns compact records without sensitive "
            "fields."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search keyword: city, station, flight number, airline, operator"
                    ),
                },
                "record_type": {
                    "type": "string",
                    "enum": ["flight", "train", "other"],
                    "description": "Filter by transport type, or omit to search all",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
        },
        permission=ToolPermission.READ,
        read=_search_records,
    ),
    "get_statistics": ToolDef(
        name="get_statistics",
        description=(
            "Return the user's travel statistics: totals (countries, cities, "
            "journeys, distance, flights, trains, transports, trips) and "
            "breakdowns by month, airline, and airport."
        ),
        parameters={"type": "object", "properties": {}},
        permission=ToolPermission.READ,
        read=_get_statistics,
    ),
    "get_record": ToolDef(
        name="get_record",
        description=(
            "Get a single transport record by its id. Returns common fields "
            "(never sensitive PNR/ticket/credential data)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "The record UUID"},
            },
            "required": ["record_id"],
        },
        permission=ToolPermission.READ,
        read=_get_record,
    ),
    "lookup_flight": ToolDef(
        name="lookup_flight",
        description=(
            "Look up live flight information by flight number and date. Returns "
            "airline code/name (incl. Chinese name), origin/destination airports and "
            "names, scheduled and actual times, terminals, gates, check-in desk, "
            "baggage belt, aircraft model/registration, timezones, status, and "
            "distance. Use this BEFORE calling create_transport when the user "
            "mentions a flight number, then copy EVERY non-null field into the "
            "create_transport proposal. If source is 'local', only the airline "
            "code/name was inferred and route/times are unknown — ask the user for "
            "those details."
        ),
        parameters={
            "type": "object",
            "properties": {
                "flight_number": {
                    "type": "string",
                    "description": "Flight number with airline code, e.g. CX659, CA1234",
                },
                "date": {
                    "type": "string",
                    "description": "Flight date YYYY-MM-DD. Defaults to today.",
                },
            },
            "required": ["flight_number"],
        },
        permission=ToolPermission.READ,
        read=_lookup_flight,
    ),
    "create_transport": ToolDef(
        name="create_transport",
        description=(
            "Propose creating a new transport record (flight, train, or other). "
            "The user must confirm before anything is saved. Provide origin, "
            "destination, and EVERY other field you can determine — do not leave "
            "fields empty when you can infer them. Always derive a value for "
            "'status' from the dates. After proposing, summarize and ask the user "
            "to confirm."
        ),
        parameters={
            "type": "object",
            "properties": {
                "record_type": {
                    "type": "string",
                    "enum": ["flight", "train", "other"],
                    "description": "Type of transport",
                },
                "data": {
                    "type": "object",
                    "description": (
                        "All known fields. Fill EVERY field you can determine from the "
                        "user's message, a lookup_flight result, or an image — never omit a "
                        "field you can infer. See the FIELD INFERENCE rules in the system "
                        "prompt for how to derive status, airline_code, train_type, currency, "
                        "timezones, etc."
                    ),
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "Origin airport / IATA code / station / city",
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination airport / IATA code / station / city",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["scheduled", "completed"],
                            "description": (
                                "Infer from the dates: 'completed' if the arrival time is "
                                "already in the past, otherwise 'scheduled'."
                            ),
                        },
                        "departure_time": {
                            "type": "string",
                            "description": (
                                "ISO 8601 datetime WITH timezone offset, "
                                "e.g. 2026-09-26T08:00:00+08:00"
                            ),
                        },
                        "arrival_time": {
                            "type": "string",
                            "description": (
                                "ISO 8601 datetime WITH timezone offset, "
                                "e.g. 2026-09-26T12:30:00+08:00"
                            ),
                        },
                        "actual_departure_time": {
                            "type": "string",
                            "description": (
                                "Actual/between departure time, ISO 8601 with offset (if known)"
                            ),
                        },
                        "actual_arrival_time": {
                            "type": "string",
                            "description": "Actual arrival time, ISO 8601 with offset (if known)",
                        },
                        "departure_timezone": {
                            "type": "string",
                            "description": "Origin timezone, e.g. Asia/Shanghai or +08:00",
                        },
                        "arrival_timezone": {
                            "type": "string",
                            "description": "Destination timezone, e.g. Asia/Tokyo or +09:00",
                        },
                        "carrier": {
                            "type": "string",
                            "description": "Airline / rail operator name",
                        },
                        "airline_code": {
                            "type": "string",
                            "description": (
                                "IATA airline code, e.g. CX. Derive from the flight number prefix."
                            ),
                        },
                        "service_number": {
                            "type": "string",
                            "description": "Flight / train / service number, e.g. CX659, G1234",
                        },
                        "cabin_class": {
                            "type": "string",
                            "description": "Cabin / seat class, e.g. economy, business, 二等座",
                        },
                        "seat": {"type": "string", "description": "Seat number, e.g. 12A"},
                        "departure_terminal": {"type": "string"},
                        "departure_gate": {
                            "type": "string",
                            "description": "Departure gate (flight) or platform (train)",
                        },
                        "arrival_terminal": {"type": "string"},
                        "arrival_gate": {
                            "type": "string",
                            "description": "Arrival gate or platform",
                        },
                        "check_in_desk": {
                            "type": "string",
                            "description": "Check-in counter / desk",
                        },
                        "baggage_belt": {
                            "type": "string",
                            "description": "Baggage claim belt",
                        },
                        "aircraft_model": {"type": "string", "description": "e.g. A350, B787"},
                        "aircraft_reg": {"type": "string", "description": "Aircraft registration"},
                        "train_type": {
                            "type": "string",
                            "description": (
                                "Train category derived from the number's leading letter "
                                "(e.g. G=高铁, D=动车, Z=直达, T=特快, K=快速, C=城际)."
                            ),
                        },
                        "carriage": {
                            "type": "string",
                            "description": "Train carriage / coach number",
                        },
                        "seat_type": {
                            "type": "string",
                            "description": "Train seat type, e.g. 商务座/一等座/二等座",
                        },
                        "ticket_type": {
                            "type": "string",
                            "description": "Train ticket type, e.g. 成人票/学生票",
                        },
                        "vehicle_type": {
                            "type": "string",
                            "description": "For other transport: bus, ferry, taxi, etc.",
                        },
                        "booking_reference": {
                            "type": "string",
                            "description": (
                                "PNR / booking reference. SENSITIVE — extract from image only."
                            ),
                        },
                        "ticket_number": {
                            "type": "string",
                            "description": ("Ticket number. SENSITIVE — extract from image only."),
                        },
                        "price": {"type": "number"},
                        "currency": {
                            "type": "string",
                            "description": (
                                "ISO 4217 code, e.g. CNY, USD, HKD. Infer from "
                                "locale/destination if not stated."
                            ),
                        },
                        "distance": {"type": "number", "description": "Distance in km"},
                        "notes": {"type": "string"},
                    },
                    "required": ["origin", "destination"],
                },
            },
            "required": ["record_type", "data"],
        },
        permission=ToolPermission.WRITE,
        proposal=_create_transport_proposal,
    ),
    "delete_transport": ToolDef(
        name="delete_transport",
        description=(
            "Propose deleting a transport record by id. The user must confirm before deletion."
        ),
        parameters={
            "type": "object",
            "properties": {
                "record_type": {
                    "type": "string",
                    "enum": ["flight", "train", "other"],
                },
                "record_id": {"type": "string", "description": "The record UUID to delete"},
            },
            "required": ["record_id", "record_type"],
        },
        permission=ToolPermission.DESTRUCTIVE,
        proposal=_delete_transport_proposal,
    ),
}


def tool_schemas() -> list[dict]:
    """OpenAI-compatible tool definitions for the chat completions API."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in TOOLS.values()
    ]

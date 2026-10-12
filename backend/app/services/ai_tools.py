"""AI tool registry (spec #31, #32, #33).

All tools are bound to the current user (spec #34). READ tools execute
immediately and feed results back into the conversation. WRITE and DESTRUCTIVE
tools never execute — they become ``AiProposal`` objects returned to the
frontend for explicit user confirmation (spec #69, #93).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from app.schemas.ai import AiProposal
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
        "departure_time": record.departure_time.isoformat() if record.departure_time else None,
        "arrival_time": record.arrival_time.isoformat() if record.arrival_time else None,
        "status": record.status,
        "distance_km": float(record.distance) if record.distance else None,
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
        "origin_iata": result.origin_iata,
        "destination_iata": result.destination_iata,
        "origin_name": result.origin_name,
        "destination_name": result.destination_name,
        "departure_time": result.departure_time.isoformat() if result.departure_time else None,
        "arrival_time": result.arrival_time.isoformat() if result.arrival_time else None,
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


def _create_transport_proposal(args: dict) -> AiProposal:
    record_type = args.get("record_type") or args.get("type") or "other"
    data = args.get("data", {})
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
            "airline, origin/destination airports, scheduled times, and status "
            "from an external flight data provider. Use this BEFORE calling "
            "create_transport when the user mentions a flight number — the "
            "returned data should be used to fill the create_transport proposal. "
            "If source is 'local', only the airline code/name was inferred and "
            "route/times are unknown — ask the user for those details."
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
            "destination, and as many fields as known."
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
                    "properties": {
                        "origin": {"type": "string", "description": "Origin airport/station/city"},
                        "destination": {
                            "type": "string",
                            "description": "Destination airport/station/city",
                        },
                        "departure_time": {"type": "string", "description": "ISO 8601 datetime"},
                        "arrival_time": {"type": "string", "description": "ISO 8601 datetime"},
                        "carrier": {"type": "string", "description": "Airline/operator name"},
                        "airline_code": {
                            "type": "string",
                            "description": "IATA airline code, e.g. CX",
                        },
                        "service_number": {
                            "type": "string",
                            "description": "Flight/train/service number",
                        },
                        "seat": {"type": "string"},
                        "vehicle_type": {
                            "type": "string",
                            "description": "For other transport: bus, ferry, taxi, etc.",
                        },
                        "train_type": {"type": "string"},
                        "cabin_class": {"type": "string"},
                        "price": {"type": "number"},
                        "currency": {"type": "string"},
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

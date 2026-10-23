"""Duplicate detection for transport records (spec #41)."""

from datetime import UTC, datetime
from typing import Any


def iso_date(value: Any) -> str:
    """Convert a datetime/date to ISO date only (for dedup)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).date().isoformat()
    if hasattr(value, "date"):  # datetime.date
        return value.isoformat()
    return str(value)


def iso_full(value: Any) -> str:
    """Convert a datetime/date to full ISO format (for export)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if hasattr(value, "date"):  # datetime.date
        return value.isoformat()
    return str(value)


def record_signature(*, record_type: str, payload: dict[str, Any]) -> str:
    """
    Compute the deduplication fingerprint per spec #41.

    Flight: date + carrier + flight_number + origin + destination
    Train:  date + operator + train_number + origin + destination
    Other:  date + carrier + service_number + origin + destination (closest match)
    """
    dep_date = iso_date(payload.get("departure_time"))

    # Flights use "carrier", trains use "operator" — both live in `carrier`.
    carrier = str(payload.get("carrier") or "").strip().lower()
    number = str(payload.get("service_number") or "").strip().upper()

    origin = str(payload.get("origin") or "").strip().lower()
    destination = str(payload.get("destination") or "").strip().lower()

    return "|".join([record_type, dep_date, carrier, number, origin, destination])


def record_signature_from_model(record: Any) -> str:
    """Compute signature from a TransportRecord ORM model."""
    dep_date = iso_date(record.departure_time)

    carrier = str(record.carrier or "").strip().lower()
    number = str(record.service_number or "").strip().upper()
    origin = str(record.origin or "").strip().lower()
    destination = str(record.destination or "").strip().lower()

    return "|".join([record.type, dep_date, carrier, number, origin, destination])
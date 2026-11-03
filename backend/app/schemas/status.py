"""Canonical status vocabularies shared by records, hotels and trips.

DB columns stay permissive ``String(20)`` — legacy rows may hold free-form
values and reads must never fail. Every *write* path (REST create/update, AI
proposals, CSV/JSON import) validates or normalizes against these literals so
no new junk status can enter the system.

Vocabularies mirror what the AI tool schemas already advertise (``ai_tools``)
and what the UI status badges render (``web/src/components/status-badge.tsx``).
"""

from typing import Literal

RecordStatus = Literal["scheduled", "completed", "cancelled"]
TripStatus = Literal["planned", "ongoing", "completed", "cancelled"]

RECORD_STATUSES: tuple[str, ...] = ("scheduled", "completed", "cancelled")
TRIP_STATUSES: tuple[str, ...] = ("planned", "ongoing", "completed", "cancelled")

# Aliases seen in imports and external provider payloads → canonical value.
# Kept in one place so flight enrichment and data import cannot drift apart.
_RECORD_ALIASES = {
    "planned": "scheduled",
    "active": "scheduled",
    "departed": "scheduled",
    "en-route": "scheduled",
    "enroute": "scheduled",
    "delayed": "scheduled",
    "boarding": "scheduled",
    "计划": "scheduled",
    "起飞": "scheduled",
    "landed": "completed",
    "arrived": "completed",
    "arrival": "completed",
    "到达": "completed",
    "落地": "completed",
    "canceled": "cancelled",
    "cancel": "cancelled",
    "取消": "cancelled",
}

_TRIP_ALIASES = {
    "scheduled": "planned",
    "upcoming": "planned",
    "active": "ongoing",
    "current": "ongoing",
    "进行中": "ongoing",
    "done": "completed",
    "finished": "completed",
    "结束": "completed",
    "canceled": "cancelled",
    "取消": "cancelled",
}


def canonical_record_status(value: object) -> RecordStatus | None:
    """Map a free-form/provider status onto the record vocabulary.

    Returns ``None`` for empty or unknown values so callers can decide whether
    to fall back (imports) or leave the field unset (provider merges).
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in RECORD_STATUSES:
        return text  # type: ignore[return-value]
    return _RECORD_ALIASES.get(text)  # type: ignore[return-value]


def normalize_record_status(value: object, default: RecordStatus = "scheduled") -> RecordStatus:
    """Like :func:`canonical_record_status` but never returns ``None``."""
    return canonical_record_status(value) or default


def canonical_trip_status(value: object) -> TripStatus | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in TRIP_STATUSES:
        return text  # type: ignore[return-value]
    return _TRIP_ALIASES.get(text)  # type: ignore[return-value]


def normalize_trip_status(value: object, default: TripStatus = "planned") -> TripStatus:
    return canonical_trip_status(value) or default

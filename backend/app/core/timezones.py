"""Timezone normalization.

Flight providers are not consistent: AeroDataBox returns IANA names
("Asia/Shanghai"), VariFlight returns UTC offsets ("+08:00"), and the time the
UI used to be a free-text input so users could type anything. Everything
downstream — the AI agent, the export bundle, the IANA dropdown — expects a
single IANA name, so every timezone that enters the system is funneled through
``normalize_timezone``.

Offsets are mapped to a readable, DST-free IANA representative for the common
flight corridors; whole-hour offsets without a curated entry fall back to the
``Etc/GMT±N`` family (sign-inverted by IANA convention), and truly exotic
values are returned unchanged so we never silently drop data.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = ["normalize_timezone", "in_timezone"]


def in_timezone(value: datetime, timezone: str | None) -> datetime:
    """Render an instant in its location's zone; legacy/invalid zones use UTC.

    SQLite returns naive datetimes for our UTC columns, unlike PostgreSQL.
    Never let the host timezone determine the calendar date of those values.
    """
    instant = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    try:
        zone = ZoneInfo(timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return instant.astimezone(zone)


# Readable, DST-free representatives for the offsets a flight provider emits.
# Picked for the corridors a CN traveller actually flies (CN/JP/SG/HK/EU/US),
# so the dropdown shows a sensible name rather than "Etc/GMT-8".
_OFFSET_TO_IANA: dict[str, str] = {
    "+00:00": "UTC",
    "+01:00": "Africa/Lagos",
    "+02:00": "Africa/Johannesburg",
    "+03:00": "Europe/Moscow",
    "+03:30": "Asia/Tehran",
    "+04:00": "Asia/Dubai",
    "+04:30": "Asia/Kabul",
    "+05:00": "Asia/Tashkent",
    "+05:30": "Asia/Kolkata",
    "+05:45": "Asia/Kathmandu",
    "+06:00": "Asia/Dhaka",
    "+06:30": "Asia/Yangon",
    "+07:00": "Asia/Bangkok",
    "+08:00": "Asia/Shanghai",
    "+08:45": "Australia/Eucla",
    "+09:00": "Asia/Tokyo",
    "+09:30": "Australia/Darwin",
    "+10:00": "Australia/Brisbane",
    "+10:30": "Australia/Lord_Howe",
    "+11:00": "Pacific/Pohnpei",
    "+12:00": "Pacific/Tarawa",
    "+12:45": "Pacific/Chatham",
    "-03:00": "America/Sao_Paulo",
    "-03:30": "America/St_Johns",
    "-04:00": "America/Manaus",
    "-05:00": "America/Bogota",
    "-06:00": "America/Regina",
    "-07:00": "America/Phoenix",
    "-08:00": "Pacific/Pitcairn",
    "-09:00": "Pacific/Gambier",
    "-09:30": "Pacific/Marquesas",
    "-10:00": "Pacific/Honolulu",
}

# "+08:00", "+8", "+0800" — providers emit several shapes.
_OFFSET_RE = re.compile(r"^([+-])(\d{1,2}):?(\d{2})?$")


def _etc_gmt(hours: int) -> str:
    # IANA Etc/GMT signs are inverted: Etc/GMT-8 == UTC+8.
    if hours == 0:
        return "UTC"
    return f"Etc/GMT{'-' if hours > 0 else '+'}{abs(hours)}"


def normalize_timezone(value: str | None) -> str | None:
    """Coerce a timezone string to an IANA name when possible.

    Returns ``None`` for blank input and leaves unrecognized values untouched
    (the column still caps at 64 chars); providers and the UI keep working
    instead of throwing on a value we cannot translate.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    # Already a valid IANA name — keep it.
    try:
        ZoneInfo(text)
        return text
    except (ZoneInfoNotFoundError, ValueError):
        pass

    match = _OFFSET_RE.match(text)
    if match:
        sign = match.group(1)
        hh = int(match.group(2))
        mm = int(match.group(3) or 0)
        key = f"{sign}{hh:02d}:{mm:02d}"
        if key in _OFFSET_TO_IANA:
            return _OFFSET_TO_IANA[key]
        if mm == 0:
            return _etc_gmt(hh if sign == "+" else -hh)

    return text

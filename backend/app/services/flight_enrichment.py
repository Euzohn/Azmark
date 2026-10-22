"""Enrich a flight number: local airline inference + optional external lookup.

Remote data comes only from configured FlightProviders whose keys the user
stored encrypted (spec #66). Provider failures never surface to the caller;
they degrade to the local airline result.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from logging import getLogger

import httpx
from sqlalchemy.orm import Session

import app.providers as providers
from app.core.timezones import normalize_timezone
from app.providers.base import FlightLookupResult
from app.schemas.flight_lookup import FlightLookupResponse
from app.services import reference
from app.services.data_source import DataSourceService
from app.services.provider_keys import ProviderKeyStore

logger = getLogger(__name__)

# Human-readable provider sites for DataSource provenance (spec #22/#37).
_PROVIDER_URLS = {
    "aerodatabox": "https://aerodatabox.com",
    "aviationstack": "https://aviationstack.com",
    "variflight": "https://www.variflight.com",
}
_PROVIDER_CONFIDENCE = {
    "aerodatabox": 0.9,
    "variflight": 0.85,
    "aviationstack": 0.6,
}

# Fields filled from lower-confidence sources only when the better source omitted
# them (never overwriting a value that is already known).
_FILL_FIELDS = (
    "airline_code",
    "airline_name",
    "airline_name_zh",
    "origin_iata",
    "destination_iata",
    "origin_name",
    "destination_name",
    "departure_time",
    "arrival_time",
    "actual_departure_time",
    "actual_arrival_time",
    "departure_terminal",
    "departure_gate",
    "arrival_terminal",
    "arrival_gate",
    "check_in_desk",
    "baggage_belt",
    "aircraft_model",
    "aircraft_reg",
    "departure_timezone",
    "arrival_timezone",
    "aircraft",
    "status",
    "distance",
)

# Discrete fields where providers must agree; a mismatch is worth surfacing.
_CONFLICT_FIELDS = (
    "origin_iata",
    "destination_iata",
    "departure_terminal",
    "arrival_terminal",
    "departure_gate",
    "arrival_gate",
    "status",
)
_TIME_CONFLICT_FIELDS = (
    "departure_time",
    "arrival_time",
    "actual_departure_time",
    "actual_arrival_time",
)
# Providers report estimates vs actuals with slight skew; only material gaps count.
_TIME_CONFLICT_TOLERANCE = timedelta(minutes=30)


def _priority(name: str) -> float:
    return _PROVIDER_CONFIDENCE.get(name, 0.5)


def _ordered_provider_names(available: dict[str, str]) -> list[str]:
    """Configured providers, most trustworthy first (spec #66)."""
    names = [name for name in providers.REGISTERED_PROVIDERS if name in available]
    return sorted(names, key=_priority, reverse=True)


class ProviderNotFoundError(Exception):
    """Requested provider name is not registered (spec #66)."""


_STATUS_ALIASES = {
    "scheduled": "scheduled",
    "planned": "scheduled",
    "active": "scheduled",
    "departed": "scheduled",
    "en-route": "scheduled",
    "enroute": "scheduled",
    "delayed": "scheduled",
    "boarding": "scheduled",
    "计划": "scheduled",
    "起飞": "scheduled",
    "completed": "completed",
    "landed": "completed",
    "arrived": "completed",
    "arrival": "completed",
    "到达": "completed",
    "落地": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "cancel": "cancelled",
    "取消": "cancelled",
}


def _normalize_status(raw: str | None) -> str | None:
    """Map provider-specific states onto the record's status vocabulary."""
    if not raw:
        return None
    return _STATUS_ALIASES.get(str(raw).strip().lower())


def _merge(local: dict, remote: FlightLookupResult | None) -> FlightLookupResponse:
    airline = local.get("airline")
    result = FlightLookupResponse(
        flight_number=local["flight_number"],
        airline_code=local.get("airline_code"),
        airline_name=airline.get("name") if airline else None,
        airline_name_zh=airline.get("name_zh") if airline else None,
        source="local",
    )
    if remote is not None:
        result.source = remote.provider
        local_code = result.airline_code
        result.airline_code = remote.airline_code or local_code
        same_airline = not (
            remote.airline_code and local_code and remote.airline_code != local_code
        )
        if same_airline:
            # The local reference is curated ("中国东方航空"); providers often
            # return the registered legal name ("中国东方航空股份有限公司").
            # Keep the short local name and only fill gaps from the provider.
            result.airline_name = result.airline_name or remote.airline_name
            result.airline_name_zh = result.airline_name_zh or remote.airline_name_zh
        else:
            # The provider corrected the prefix-inferred carrier, so the local
            # names describe a different airline and must not be kept.
            result.airline_name = remote.airline_name
            result.airline_name_zh = remote.airline_name_zh
        result.origin_iata = remote.origin_iata
        result.destination_iata = remote.destination_iata
        result.origin_name = remote.origin_name
        result.destination_name = remote.destination_name
        result.departure_time = remote.departure_time
        result.arrival_time = remote.arrival_time
        result.actual_departure_time = remote.actual_departure_time
        result.actual_arrival_time = remote.actual_arrival_time
        result.departure_terminal = remote.departure_terminal
        result.departure_gate = remote.departure_gate
        result.arrival_terminal = remote.arrival_terminal
        result.arrival_gate = remote.arrival_gate
        result.check_in_desk = remote.check_in_desk
        result.baggage_belt = remote.baggage_belt
        result.aircraft_model = remote.aircraft_model
        result.aircraft_reg = remote.aircraft_reg
        # VariFlight reports offsets ("+08:00"); the rest of the app only
        # understands IANA names, so normalize at the aggregation point rather
        # than inside the provider (which stays faithful to its source).
        result.departure_timezone = normalize_timezone(remote.departure_timezone)
        result.arrival_timezone = normalize_timezone(remote.arrival_timezone)
        result.aircraft = remote.aircraft
        result.status = _normalize_status(str(remote.status) if remote.status else None)
        result.distance = float(remote.distance) if remote.distance is not None else None
    return result


@dataclass
class FlightFieldConflict:
    """A field where configured providers returned different values."""

    field: str
    values: dict[str, str]


@dataclass
class MergedFlightLookup:
    """Best-effort merge of every configured provider (spec #31/#66)."""

    result: FlightLookupResponse
    sources: list[dict]
    conflicts: list[FlightFieldConflict]


def _display(field: str, value: object) -> str:
    if field == "status":
        return _normalize_status(str(value)) or str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalized_code(field: str, value: str) -> str:
    text = str(value).strip().upper()
    # "T1" and "1" denote the same terminal; that is not a disagreement.
    if field.endswith("terminal") and text.startswith("T") and text[1:].isdigit():
        return text[1:]
    return text


def _coerce(field: str, value: object) -> object:
    """Normalise a raw provider value when filling a gap from a weaker source."""
    if field == "status":
        return _normalize_status(str(value))
    if field in ("departure_timezone", "arrival_timezone"):
        return normalize_timezone(value)  # type: ignore[arg-type]
    if field == "distance":
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    return value


def _merge_sources(
    local: dict, found: list[tuple[str, FlightLookupResult]]
) -> FlightLookupResponse:
    """Merge provider results by confidence, keeping the best value per field."""
    ordered = sorted(found, key=lambda item: _priority(item[0]), reverse=True)
    primary_name, primary = ordered[0]
    merged = _merge(local, primary)
    merged.source = primary_name
    for _name, remote in ordered[1:]:
        for field in _FILL_FIELDS:
            if getattr(merged, field) is not None:
                continue
            # Never attach a name from a source that identified a different
            # airline/airport — that would silently mismatch the code we kept.
            if field in ("airline_name", "airline_name_zh"):
                if remote.airline_code and merged.airline_code != remote.airline_code:
                    continue
            elif field == "origin_name":
                if remote.origin_iata and merged.origin_iata != remote.origin_iata:
                    continue
            elif field == "destination_name":
                if remote.destination_iata and merged.destination_iata != remote.destination_iata:
                    continue
            value = _coerce(field, getattr(remote, field))
            if value is not None:
                setattr(merged, field, value)
    return merged


def _detect_conflicts(
    found: list[tuple[str, FlightLookupResult]],
) -> list[FlightFieldConflict]:
    """Report fields where providers disagree (material differences only)."""
    conflicts: list[FlightFieldConflict] = []
    for field in _CONFLICT_FIELDS:
        values = {
            name: _display(field, getattr(remote, field))
            for name, remote in found
            if getattr(remote, field) not in (None, "")
        }
        if len(values) < 2:
            continue
        if len({_normalized_code(field, value) for value in values.values()}) > 1:
            conflicts.append(FlightFieldConflict(field=field, values=values))

    for field in _TIME_CONFLICT_FIELDS:
        points = {
            name: value
            for name, remote in found
            if isinstance(value := getattr(remote, field), datetime) and value.tzinfo is not None
        }
        if len(points) < 2:
            continue
        reference_instant = next(iter(points.values()))
        if any(
            abs(point - reference_instant) > _TIME_CONFLICT_TOLERANCE for point in points.values()
        ):
            conflicts.append(
                FlightFieldConflict(
                    field=field,
                    values={name: _display(field, value) for name, value in points.items()},
                )
            )
    return conflicts


class FlightEnrichmentService:
    def __init__(self, db: Session) -> None:
        self.keys = ProviderKeyStore(db)
        self.sources = DataSourceService(db)

    def _record_source(
        self,
        *,
        user_id: uuid.UUID,
        flight_number: str,
        date: date,
        result: FlightLookupResponse,
    ) -> None:
        """Persist where this external flight result came from (spec #22/#37)."""
        if not result.source or result.source == "local":
            return
        try:
            self.sources.record(
                user_id=user_id,
                source_type="api",
                source_name=f"{flight_number} · {date.isoformat()}",
                source_url=_PROVIDER_URLS.get(result.source),
                provider=result.source,
                confidence=_PROVIDER_CONFIDENCE.get(result.source, 0.5),
                metadata={
                    "flight_number": flight_number,
                    "date": date.isoformat(),
                    "origin": result.origin_iata,
                    "destination": result.destination_iata,
                    "status": result.status,
                },
            )
        except Exception as exc:  # noqa: BLE001 - provenance must not break lookups
            logger.warning("FlightLookup: could not record data source: %r", exc)

    async def lookup(
        self,
        *,
        user_id: uuid.UUID,
        flight_number: str,
        date: date,
        provider: str | None = None,
    ) -> FlightLookupResponse:
        local = reference.lookup_flight_number(flight_number)
        number = local["flight_number"]
        if provider is not None and provider not in providers.REGISTERED_PROVIDERS:
            raise ProviderNotFoundError(provider)

        available = self.keys.get_decrypted(user_id=user_id)
        order = [provider] if provider else _ordered_provider_names(available)
        if not order:
            logger.info(
                "FlightLookup: no provider key configured (user=%s) — local fallback for %s",
                user_id,
                number,
            )
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            for name in order:
                api_key = available.get(name)
                if not api_key:
                    continue
                provider_obj = providers.REGISTERED_PROVIDERS[name](api_key, client=client)
                try:
                    remote = await provider_obj.lookup(number, date=date)
                except Exception as exc:
                    logger.warning(
                        "FlightLookup: provider %s raised %r for %s — local fallback",
                        name,
                        exc,
                        number,
                    )
                    remote = None
                if remote is not None:
                    logger.info("FlightLookup: %s returned a result for %s", name, number)
                    result = _merge(local, remote)
                    self._record_source(
                        user_id=user_id,
                        flight_number=number,
                        date=date,
                        result=result,
                    )
                    return result
                logger.info("FlightLookup: %s returned no result for %s", name, number)
        logger.info("FlightLookup: local-only result for %s", number)
        return _merge(local, None)

    async def _query_all(
        self,
        *,
        user_id: uuid.UUID,
        number: str,
        date: date,
        order: list[str],
        available: dict[str, str],
        local: dict,
        log_label: str,
    ) -> list[tuple[str, FlightLookupResult | None, FlightLookupResponse | None]]:
        """Run every provider concurrently; order is preserved in the result."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            return list(
                await asyncio.gather(
                    *(
                        self._query_one(
                            name=name,
                            api_key=available[name],
                            client=client,
                            number=number,
                            date=date,
                            user_id=user_id,
                            local=local,
                            log_label=log_label,
                        )
                        for name in order
                    )
                )
            )

    async def _query_one(
        self,
        *,
        name: str,
        api_key: str,
        client: httpx.AsyncClient,
        number: str,
        date: date,
        user_id: uuid.UUID,
        local: dict,
        log_label: str,
    ) -> tuple[str, FlightLookupResult | None, FlightLookupResponse | None]:
        """Query a single provider; failures degrade to "no result" (spec #66)."""
        provider_obj = providers.REGISTERED_PROVIDERS[name](api_key, client=client)
        try:
            remote = await provider_obj.lookup(number, date=date)
        except Exception as exc:  # noqa: BLE001 - one bad source must not break the rest
            logger.warning(
                "%s: provider %s raised %r for %s — skipped",
                log_label,
                name,
                exc,
                number,
            )
            return name, None, None
        if remote is None:
            logger.info("%s: %s returned no result for %s", log_label, name, number)
            return name, None, None
        logger.info("%s: %s returned a result for %s", log_label, name, number)
        merged = _merge(local, remote)
        self._record_source(
            user_id=user_id,
            flight_number=number,
            date=date,
            result=merged,
        )
        return name, remote, merged

    async def lookup_all(
        self,
        *,
        user_id: uuid.UUID,
        flight_number: str,
        date: date,
    ) -> list[dict]:
        """Query every configured provider independently; returns all results.

        Unlike ``lookup``, this does not stop at the first match — the caller
        (e.g. the flight form's compare view) wants to see what each provider
        returned so the user can pick one. Providers are queried concurrently
        and listed most trustworthy first.
        """
        local = reference.lookup_flight_number(flight_number)
        number = local["flight_number"]
        available = self.keys.get_decrypted(user_id=user_id)
        order = _ordered_provider_names(available)
        if not order:
            logger.info(
                "FlightLookupAll: no provider key configured (user=%s) for %s",
                user_id,
                number,
            )
            return []
        pairs = await self._query_all(
            user_id=user_id,
            number=number,
            date=date,
            order=order,
            available=available,
            local=local,
            log_label="FlightLookupAll",
        )
        return [{"provider": name, "data": merged} for name, _raw, merged in pairs]

    async def lookup_merged(
        self,
        *,
        user_id: uuid.UUID,
        flight_number: str,
        date: date,
    ) -> MergedFlightLookup:
        """Cross-check every configured provider and merge by confidence.

        This is what the AI tool uses: it needs the best value per field plus
        any disagreement between sources, so the assistant can tell the user
        instead of silently trusting one vendor (spec #31/#66/#70).
        """
        local = reference.lookup_flight_number(flight_number)
        number = local["flight_number"]
        available = self.keys.get_decrypted(user_id=user_id)
        order = _ordered_provider_names(available)
        if not order:
            logger.info(
                "FlightLookupMerged: no provider key configured (user=%s) — local fallback for %s",
                user_id,
                number,
            )
            return MergedFlightLookup(result=_merge(local, None), sources=[], conflicts=[])

        pairs = await self._query_all(
            user_id=user_id,
            number=number,
            date=date,
            order=order,
            available=available,
            local=local,
            log_label="FlightLookupMerged",
        )
        sources = [
            {"provider": name, "confidence": _priority(name), "data": merged}
            for name, _raw, merged in pairs
        ]
        found = [(name, raw) for name, raw, _merged in pairs if raw is not None]
        if not found:
            return MergedFlightLookup(
                result=_merge(local, None),
                sources=sources,
                conflicts=[],
            )
        return MergedFlightLookup(
            result=_merge_sources(local, found),
            sources=sources,
            conflicts=_detect_conflicts(found),
        )

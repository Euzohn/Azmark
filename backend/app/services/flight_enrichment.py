"""Enrich a flight number: local airline inference + optional external lookup.

Remote data comes only from configured FlightProviders whose keys the user
stored encrypted (spec #66). Provider failures never surface to the caller;
they degrade to the local airline result.
"""

import uuid
from datetime import date
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
        order = (
            [provider]
            if provider
            else [name for name in providers.REGISTERED_PROVIDERS if name in available]
        )
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
        returned so the user can pick one.
        """
        local = reference.lookup_flight_number(flight_number)
        number = local["flight_number"]
        available = self.keys.get_decrypted(user_id=user_id)
        order = [name for name in providers.REGISTERED_PROVIDERS if name in available]
        results: list[dict] = []
        if not order:
            logger.info(
                "FlightLookupAll: no provider key configured (user=%s) for %s",
                user_id,
                number,
            )
            return results
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
                        "FlightLookupAll: provider %s raised %r for %s",
                        name,
                        exc,
                        number,
                    )
                    remote = None
                if remote is not None:
                    logger.info("FlightLookupAll: %s returned a result for %s", name, number)
                    merged = _merge(local, remote)
                    self._record_source(
                        user_id=user_id,
                        flight_number=number,
                        date=date,
                        result=merged,
                    )
                    results.append({"provider": name, "data": merged})
                else:
                    logger.info("FlightLookupAll: %s returned no result for %s", name, number)
                    results.append({"provider": name, "data": None})
        return results

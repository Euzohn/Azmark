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
from app.providers.base import FlightLookupResult
from app.schemas.flight_lookup import FlightLookupResponse
from app.services import reference
from app.services.provider_keys import ProviderKeyStore

logger = getLogger(__name__)


class ProviderNotFoundError(Exception):
    """Requested provider name is not registered (spec #66)."""


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
        result.airline_code = remote.airline_code or result.airline_code
        result.airline_name = remote.airline_name or result.airline_name
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
        result.departure_timezone = remote.departure_timezone
        result.arrival_timezone = remote.arrival_timezone
        result.aircraft = remote.aircraft
        result.status = str(remote.status) if remote.status else None
        result.distance = float(remote.distance) if remote.distance is not None else None
    return result


class FlightEnrichmentService:
    def __init__(self, db: Session) -> None:
        self.keys = ProviderKeyStore(db)

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
                    return _merge(local, remote)
                logger.info("FlightLookup: %s returned no result for %s", name, number)
        logger.info("FlightLookup: local-only result for %s", number)
        return _merge(local, None)

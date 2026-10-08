"""Enrich a flight number: local airline inference + optional external lookup.

Remote data comes only from configured FlightProviders whose keys the user
stored encrypted (spec #66). Provider failures never surface to the caller;
they degrade to the local airline result.
"""

import uuid
from datetime import date

import httpx
from sqlalchemy.orm import Session

import app.providers as providers
from app.providers.base import FlightLookupResult
from app.schemas.flight_lookup import FlightLookupResponse
from app.services import reference
from app.services.provider_keys import ProviderKeyStore


class ProviderNotFoundError(Exception):
    """Requested provider name is not registered (spec #66)."""


def _merge(local: dict, remote: FlightLookupResult | None) -> FlightLookupResponse:
    airline = local.get("airline")
    result = FlightLookupResponse(
        flight_number=local["flight_number"],
        airline_code=local.get("airline_code"),
        airline_name=airline.get("name") if airline else None,
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
        result.aircraft = remote.aircraft
        result.status = remote.status
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
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            for name in order:
                api_key = available.get(name)
                if not api_key:
                    continue
                provider_obj = providers.REGISTERED_PROVIDERS[name](api_key, client=client)
                try:
                    remote = await provider_obj.lookup(number, date=date)
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    remote = None
                if remote is not None:
                    return _merge(local, remote)
        return _merge(local, None)

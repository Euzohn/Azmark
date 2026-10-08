"""FlightProvider abstraction (spec #66).

External flight data sources are always reached through a provider so the app
never hard-codes a vendor. A provider resolves a flight number + date into a
normalized result; callers merge it with local reference data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class FlightLookupResult:
    """Normalized flight details from an external provider (never sensitive)."""

    flight_number: str
    airline_code: str | None = None
    airline_name: str | None = None
    origin_iata: str | None = None
    destination_iata: str | None = None
    origin_name: str | None = None
    destination_name: str | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    actual_departure_time: datetime | None = None
    actual_arrival_time: datetime | None = None
    aircraft: str | None = None
    status: str | None = None
    distance: float | None = None
    provider: str = ""


class FlightProvider(ABC):
    """Base class for external flight-data providers (spec #66)."""

    name: str = ""

    @abstractmethod
    async def lookup(self, flight_number: str, *, date: date) -> FlightLookupResult | None:
        """Resolve a flight number on the given date.

        Return None when the provider has no match (e.g. unknown flight). Raise
        on hard transport/auth errors so the enrichment layer can fall back.
        """
        raise NotImplementedError

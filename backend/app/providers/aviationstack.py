"""AviationStack flight-data provider (spec #66).

Endpoint: GET {base}/flights?access_key=…&flight_iata=…&flight_date=YYYY-MM-DD.
Requires a per-user API key stored encrypted at rest (spec #35, #45). The key
is sent as a query parameter and never logged.

Response: ``{ data: [{ departure, arrival, airline, flight, aircraft, … }] }``.
Times are ISO 8601 strings with offset (e.g. ``2026-01-01T09:00:00+00:00``).
"""

from datetime import date, datetime
from logging import getLogger

import httpx

from app.core.config import settings
from app.providers.base import FlightLookupResult, FlightProvider

logger = getLogger(__name__)


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class AviationStackProvider(FlightProvider):
    name = "aviationstack"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or settings.aviationstack_base_url).rstrip("/")
        self._client = client

    async def lookup(self, flight_number: str, *, date: date) -> FlightLookupResult | None:
        if not self.api_key:
            return None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            response = await client.get(
                f"{self.base_url}/flights",
                params={
                    "access_key": self.api_key,
                    "flight_iata": flight_number,
                    "flight_date": f"{date:%Y-%m-%d}",
                },
            )
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code == 404:
            return None
        response.raise_for_status()
        try:
            payload = response.json()
            flights = (payload or {}).get("data") or []
            if not flights:
                logger.info("AviationStack: no flights for %s on %s", flight_number, date)
                return None
            return self._parse(flights[0], flight_number)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("AviationStack: parse failed: %s", exc)
            return None

    def _parse(self, flight: dict, flight_number: str) -> FlightLookupResult:
        departure = flight.get("departure") or {}
        arrival = flight.get("arrival") or {}
        airline = flight.get("airline") or {}
        aircraft = flight.get("aircraft") or {}
        return FlightLookupResult(
            flight_number=flight_number,
            airline_code=_as_str(airline.get("iata")) or _as_str(airline.get("icao")),
            airline_name=_as_str(airline.get("name")),
            origin_iata=_as_str(departure.get("iata")) or _as_str(departure.get("icao")),
            destination_iata=_as_str(arrival.get("iata")) or _as_str(arrival.get("icao")),
            origin_name=_as_str(departure.get("airport")),
            destination_name=_as_str(arrival.get("airport")),
            departure_time=_parse_datetime(departure.get("scheduled")),
            arrival_time=_parse_datetime(arrival.get("scheduled")),
            actual_departure_time=_parse_datetime(
                departure.get("actual") or departure.get("estimated")
            ),
            actual_arrival_time=_parse_datetime(
                arrival.get("actual") or arrival.get("estimated")
            ),
            departure_terminal=_as_str(departure.get("terminal")),
            departure_gate=_as_str(departure.get("gate")),
            arrival_terminal=_as_str(arrival.get("terminal")),
            arrival_gate=_as_str(arrival.get("gate")),
            baggage_belt=_as_str(arrival.get("baggage")),
            aircraft_model=_as_str(aircraft.get("model")),
            aircraft_reg=_as_str(aircraft.get("registration")),
            departure_timezone=_as_str(departure.get("timezone")),
            arrival_timezone=_as_str(arrival.get("timezone")),
            status=_as_str(flight.get("flight_status")),
            provider=self.name,
        )

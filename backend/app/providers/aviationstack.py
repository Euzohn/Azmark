"""AviationStack flight-data provider (spec #66).

Endpoint: GET {base}/flights?access_key=…&flight_iata=….  The free plan does
NOT support the ``flight_date`` query parameter (returns
``function_access_restricted``), so we fetch all flights for the IATA code and
filter by date client-side.

Response: ``{ data: [{ flight_date, departure, arrival, airline, … }] }``.
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
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(10.0), follow_redirects=True
        )
        try:
            response = await client.get(
                f"{self.base_url}/flights",
                params={
                    "access_key": self.api_key,
                    "flight_iata": flight_number,
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
            if isinstance(payload, dict) and "error" in payload:
                err = payload["error"]
                logger.warning(
                    "AviationStack API error for %s: code=%s message=%s",
                    flight_number,
                    err.get("code"),
                    err.get("message"),
                )
                return None
            flights = (payload or {}).get("data") or []
            if not flights:
                logger.info("AviationStack: no flights for %s", flight_number)
                return None
            target = f"{date:%Y-%m-%d}"
            match = next((f for f in flights if f.get("flight_date") == target), None)
            if match is None:
                match = flights[0]
                logger.info(
                    "AviationStack: no exact date match for %s on %s, "
                    "using first of %d results (date=%s)",
                    flight_number,
                    target,
                    len(flights),
                    match.get("flight_date"),
                )
            return self._parse(match, flight_number)
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
            actual_arrival_time=_parse_datetime(arrival.get("actual") or arrival.get("estimated")),
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

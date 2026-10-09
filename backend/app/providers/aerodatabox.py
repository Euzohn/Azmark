"""AeroDataBox (RapidAPI) flight-number provider.

Endpoint: GET {base}/flights/number/{number}/{date}. Requires a per-user API
key stored encrypted at rest (spec #35, #45). Auth headers are sent only to
this provider, never logged.

Response (OpenAPI v1.15): departure/arrival are FlightAirportMovementContract
with DateTimeContract objects {local, utc}: `scheduledTime` (planned),
`revisedTime` (actual/estimated at gate), `runwayTime` (actual on runway),
`predictedTime` (historical estimate). `greatCircleDistance.km` is the
route distance. `aircraft.model` is a plain string.
"""

from datetime import date, datetime
from logging import getLogger

import httpx

from app.core.config import settings
from app.providers.base import FlightLookupResult, FlightProvider

logger = getLogger(__name__)


def _parse_datetime(value: object) -> datetime | None:
    """AeroDataBox times are {local, utc}; prefer local (keeps zone offset)."""
    if not isinstance(value, dict):
        return None
    raw = value.get("local") or value.get("utc")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


class AeroDataBoxProvider(FlightProvider):
    name = "aerodatabox"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        host: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or settings.aerodatabox_base_url).rstrip("/")
        self.host = host or settings.aerodatabox_host
        self._client = client

    async def lookup(self, flight_number: str, *, date: date) -> FlightLookupResult | None:
        if not self.api_key:
            return None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            response = await client.get(
                f"{self.base_url}/flights/number/{flight_number}/{date:%Y-%m-%d}",
                headers={"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.host},
                params={
                    "withAircraftImage": "false",
                    "withTracking": "false",
                    "withCrew": "false",
                    "withFlightNumberOffset": "false",
                },
            )
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code == 404:
            logger.info("AeroDataBox: no flight for %s on %s (404)", flight_number, date)
            return None
        response.raise_for_status()
        try:
            payload = response.json()
            if isinstance(payload, list):
                flights = payload
            else:
                flights = (payload or {}).get("flights") or []
            logger.info(
                "AeroDataBox: status=%s flights=%d payload=%s",
                response.status_code,
                len(flights),
                str(payload)[:2000],
            )
            if not flights:
                logger.warning("AeroDataBox: empty flights list for %s", flight_number)
                return None
            return self._parse(flights[0], flight_number)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("AeroDataBox: parse failed: %s", exc)
            return None

    def _parse(self, flight: dict, flight_number: str) -> FlightLookupResult:
        airline = flight.get("airline") or {}
        departure = flight.get("departure") or {}
        arrival = flight.get("arrival") or {}
        dep_airport = departure.get("airport") or {}
        arr_airport = arrival.get("airport") or {}
        aircraft = flight.get("aircraft") or {}
        distance = flight.get("greatCircleDistance") or {}
        return FlightLookupResult(
            flight_number=flight_number,
            airline_code=airline.get("iata") or airline.get("icao"),
            airline_name=airline.get("name"),
            origin_iata=dep_airport.get("iata") or dep_airport.get("icao"),
            destination_iata=arr_airport.get("iata") or arr_airport.get("icao"),
            origin_name=dep_airport.get("name"),
            destination_name=arr_airport.get("name"),
            departure_time=_parse_datetime(departure.get("scheduledTime")),
            arrival_time=_parse_datetime(arrival.get("scheduledTime")),
            actual_departure_time=_parse_datetime(
                departure.get("runwayTime") or departure.get("revisedTime")
            ),
            actual_arrival_time=_parse_datetime(
                arrival.get("runwayTime") or arrival.get("revisedTime")
            ),
            aircraft=aircraft.get("model") or aircraft.get("reg"),
            status=flight.get("status"),
            distance=distance.get("km"),
            provider=self.name,
        )

"""AeroDataBox (RapidAPI) flight-number provider.

Endpoint: GET {base}/flights/number/{number}/{date}. Requires a per-user API
key stored encrypted at rest (spec #35, #45). Auth headers are sent only to
this provider, never logged.
"""

from datetime import date, datetime

import httpx

from app.core.config import settings
from app.providers.base import FlightLookupResult, FlightProvider


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
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
            return None
        response.raise_for_status()
        try:
            payload = response.json()
            flights = payload.get("flights") or []
            if not flights:
                return None
            return self._parse(flights[0], flight_number)
        except (ValueError, KeyError, TypeError):
            return None

    def _parse(self, flight: dict, flight_number: str) -> FlightLookupResult:
        airline = flight.get("airline") or {}
        departure = flight.get("departure") or {}
        arrival = flight.get("arrival") or {}
        dep_airport = departure.get("airport") or {}
        arr_airport = arrival.get("airport") or {}
        aircraft = flight.get("aircraft") or {}
        model = aircraft.get("model") or {}
        return FlightLookupResult(
            flight_number=flight_number,
            airline_code=airline.get("iata") or airline.get("icao"),
            airline_name=airline.get("name"),
            origin_iata=dep_airport.get("iata") or dep_airport.get("icao"),
            destination_iata=arr_airport.get("iata") or arr_airport.get("icao"),
            origin_name=dep_airport.get("name"),
            destination_name=arr_airport.get("name"),
            departure_time=_parse_time(departure.get("time")),
            arrival_time=_parse_time(arrival.get("time")),
            aircraft=model.get("text") or model.get("code"),
            status=flight.get("status"),
            provider=self.name,
        )

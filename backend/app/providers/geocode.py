"""MapProvider: forward-geocode a free-form place (spec #66, Map category).

Uses Nominatim (OpenStreetMap) — keyless, but its usage policy limits the
public instance to about one request per second, so geocoding is only invoked
on explicit user action, never inside a list or create hot path. Failures
degrade to ``None``; the caller decides what to tell the user. Point
``GEOCODE_BASE_URL`` at a self-hosted Nominatim to lift the public limit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# A descriptive User-Agent is required by the Nominatim usage policy.
USER_AGENT = "Azmark/0.1 (personal travel log)"


@dataclass
class GeocodeResult:
    """Normalized forward-geocoding result (never sensitive)."""

    lat: float
    lon: float
    display_name: str | None = None


class GeocodeProvider:
    """Forward geocoding through a Nominatim-compatible search endpoint."""

    name = "nominatim"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.geocode_base_url).rstrip("/")
        self._client = client

    async def search(self, query: str, *, limit: int = 1) -> GeocodeResult | None:
        query = query.strip()
        if not query:
            return None

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            response = await client.get(
                f"{self.base_url}/search",
                params={"q": query, "format": "jsonv2", "limit": limit},
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            response.raise_for_status()
            results = response.json()
        except Exception as exc:  # noqa: BLE001 - external service; degrade to None
            logger.warning("Geocode: Nominatim failed for %r: %r", query, exc)
            return None
        finally:
            if owns_client:
                await client.aclose()

        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        if not isinstance(first, dict):
            return None
        try:
            return GeocodeResult(
                lat=float(first["lat"]),
                lon=float(first["lon"]),
                display_name=first.get("display_name"),
            )
        except (KeyError, TypeError, ValueError):
            return None

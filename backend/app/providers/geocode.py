"""MapProvider: forward-geocode a free-form place (spec #66, Map category).

Geocoding runs through a small provider chain so a blocked or rate-limited
service does not break the feature:

1. **Amap** (高德) — used first when ``GEOCODE_AMAP_KEY`` is set. Best accuracy
   for Chinese addresses and reachable from mainland servers.
2. **Photon** — keyless, OSM-based, and reachable where the public Nominatim
   instance is not.
3. **Nominatim** — keyless fallback; point ``GEOCODE_BASE_URL`` at a
   self-hosted instance to avoid the public rate limit.

"Not found" returns ``None`` (the address simply did not match), while "no
provider could be reached" raises ``GeocodeUnavailableError`` so the UI can say
the service is down instead of blaming the address.

Callers that need to sanity-check matches (same street name in another country)
use ``search_candidates`` to get every candidate instead of only the first.

Geocoding is only invoked on explicit user action — never inside a list or
create hot path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.utils.geo import gcj02_to_wgs84

logger = logging.getLogger(__name__)

# A descriptive User-Agent is required by the Nominatim usage policy.
USER_AGENT = "Azmark/0.1 (personal travel log)"
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
DEFAULT_PROVIDERS = ("photon", "nominatim")


class GeocodeUnavailableError(RuntimeError):
    """Every configured provider failed to answer (network, HTTP or key error)."""


@dataclass
class GeocodeResult:
    """Normalized forward-geocoding result (never sensitive)."""

    lat: float
    lon: float
    display_name: str | None = None
    provider: str = ""


def _parse_providers(raw: str | None) -> list[str]:
    names = [part.strip().lower() for part in (raw or "").split(",") if part.strip()]
    known = [name for name in names if name in {"amap", "photon", "nominatim"}]
    return known or list(DEFAULT_PROVIDERS)


class GeocodeProvider:
    """Forward geocoding through a configurable chain of providers."""

    name = "chain"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        providers: list[str] | None = None,
        amap_key: str | None = None,
        photon_url: str | None = None,
        language: str | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.base_url = (base_url or settings.geocode_base_url).rstrip("/")
        self.photon_url = (photon_url or settings.geocode_photon_url).rstrip("/")
        self.amap_key = settings.geocode_amap_key if amap_key is None else amap_key
        self.language = (language or "").strip()
        self.timeout = timeout
        self._client = client

        raw = (settings.geocode_provider or "").strip().lower()
        names = _parse_providers(raw) if providers is None else list(providers)
        # A configured Amap key is a strong signal the deployment is in China;
        # try it first unless the operator explicitly narrowed the provider list.
        if (
            self.amap_key
            and "amap" not in names
            and providers is None
            and raw in {"", "photon,nominatim"}
        ):
            names.insert(0, "amap")
        self.providers = names

    async def search(self, query: str, *, limit: int = 1) -> GeocodeResult | None:
        """First match for ``query`` (kept for simple callers and tests)."""
        results = await self.search_candidates(query, limit=limit)
        return results[0] if results else None

    async def search_candidates(
        self,
        query: str,
        *,
        limit: int = 5,
        accept: Callable[[GeocodeResult], bool] | None = None,
    ) -> list[GeocodeResult]:
        """Candidates from the provider chain, in provider order.

        A single provider often ranks a same-named street in another country
        first; returning several lets the caller pick the one that matches the
        address's own country/city.

        ``accept`` also stops the chain early once a provider returns a
        candidate that satisfies it, so an unreachable fallback provider does
        not add its timeout to every successful lookup.
        """
        query = query.strip()
        if not query:
            return []

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(4.0, self.timeout))
        )
        reachable = False
        failures: list[str] = []
        results: list[GeocodeResult] = []
        try:
            for name in self.providers:
                try:
                    found = await self._search_with(name, client, query, limit)
                except GeocodeUnavailableError as exc:
                    failures.append(f"{name}: {exc}")
                    logger.warning("Geocode: %s unavailable for %r: %s", name, query, exc)
                    continue
                reachable = True
                results.extend(found)
                if found and (accept is None or any(accept(item) for item in found)):
                    break
        finally:
            if owns_client:
                await client.aclose()

        if not reachable and failures:
            raise GeocodeUnavailableError("; ".join(failures))
        return results

    async def _search_with(
        self, name: str, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[GeocodeResult]:
        if name == "amap":
            return await self._amap(client, query, limit)
        if name == "nominatim":
            return await self._nominatim(client, query, limit)
        return await self._photon(client, query, limit)

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str] | None = None,
    ) -> object:
        request_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            **(headers or {}),
        }
        try:
            response = await client.get(url, params=params, headers=request_headers)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GeocodeUnavailableError(str(exc)) from exc

    def _accept_language(self) -> str | None:
        if not self.language:
            return None
        if self.language.lower().startswith("zh"):
            return "zh-CN,zh;q=0.9,en;q=0.8"
        return self.language

    async def _amap(self, client: httpx.AsyncClient, query: str, limit: int) -> list[GeocodeResult]:
        if not self.amap_key:
            raise GeocodeUnavailableError("Amap key is not configured")
        payload = await self._get_json(
            client, AMAP_GEOCODE_URL, params={"address": query, "key": self.amap_key}
        )
        if not isinstance(payload, dict):
            return []
        if str(payload.get("status")) != "1":
            raise GeocodeUnavailableError(f"Amap error: {payload.get('info') or 'unknown'}")
        geocodes = payload.get("geocodes")
        if not isinstance(geocodes, list):
            return []

        results: list[GeocodeResult] = []
        for first in geocodes[:limit]:
            if not isinstance(first, dict):
                continue
            try:
                # Amap returns "lon,lat" in GCJ-02; the app stores and renders
                # WGS-84, so shift it back before returning.
                lon_raw, lat_raw = str(first["location"]).split(",", 1)
                lat, lon = gcj02_to_wgs84(float(lat_raw), float(lon_raw))
            except (KeyError, TypeError, ValueError):
                continue
            results.append(
                GeocodeResult(
                    lat=lat,
                    lon=lon,
                    display_name=first.get("formatted_address"),
                    provider="amap",
                )
            )
        return results

    async def _photon(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[GeocodeResult]:
        headers = {"Accept-Language": self._accept_language()} if self.language else None
        payload = await self._get_json(
            client,
            f"{self.photon_url}/api/",
            params={"q": query, "limit": limit},
            headers=headers,
        )
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            return []

        results: list[GeocodeResult] = []
        for first in features[:limit]:
            if not isinstance(first, dict):
                continue
            try:
                coordinates = first["geometry"]["coordinates"]
                lon, lat = coordinates[0], coordinates[1]
                props = first.get("properties") or {}
                parts = [props.get("name"), props.get("city"), props.get("country")]
                display = ", ".join(str(part) for part in parts if part) or None
                results.append(
                    GeocodeResult(
                        lat=float(lat),
                        lon=float(lon),
                        display_name=display,
                        provider="photon",
                    )
                )
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        return results

    async def _nominatim(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[GeocodeResult]:
        headers = {"Accept-Language": self._accept_language()} if self.language else None
        payload = await self._get_json(
            client,
            f"{self.base_url}/search",
            params={"q": query, "format": "jsonv2", "limit": limit},
            headers=headers,
        )
        if not isinstance(payload, list):
            return []

        results: list[GeocodeResult] = []
        for first in payload[:limit]:
            if not isinstance(first, dict):
                continue
            try:
                results.append(
                    GeocodeResult(
                        lat=float(first["lat"]),
                        lon=float(first["lon"]),
                        display_name=first.get("display_name"),
                        provider="nominatim",
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return results

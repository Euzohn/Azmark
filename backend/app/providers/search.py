"""SearchProvider abstraction (spec #37, #66).

External web search is used for train schedules (arrival time, platform),
airline/airport/station facts and travel info. Results are UNTRUSTED content:
callers must treat snippets as data, never as instructions (spec #70).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


class SearchProviderError(Exception):
    """Hard transport/auth failure from a search provider."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchProvider(ABC):
    """Base class for web search providers (spec #37)."""

    name: str = ""

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 6) -> list[SearchResult]:
        raise NotImplementedError


def _as_results(items: list[dict], max_results: int) -> list[SearchResult]:
    results: list[SearchResult] = []
    for item in items[:max_results]:
        results.append(
            SearchResult(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or item.get("link") or ""),
                snippet=str(
                    item.get("content") or item.get("snippet") or item.get("description") or ""
                ),
            )
        )
    return results


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, query: str, *, max_results: int = 6) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_answer": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise SearchProviderError("tavily request failed") from exc
        return _as_results(payload.get("results") or [], max_results)


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, query: str, *, max_results: int = 6) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": max_results},
                    headers={"X-Subscription-Token": self.api_key},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise SearchProviderError("brave request failed") from exc
        web = (payload.get("web") or {}).get("results") or []
        return _as_results(web, max_results)


class SearxngProvider(SearchProvider):
    name = "searxng"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def search(self, query: str, *, max_results: int = 6) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={"q": query, "format": "json"},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise SearchProviderError("searxng request failed") from exc
        return _as_results(payload.get("results") or [], max_results)


SEARCH_PROVIDERS: dict[str, type[SearchProvider]] = {
    TavilyProvider.name: TavilyProvider,
    BraveProvider.name: BraveProvider,
    SearxngProvider.name: SearxngProvider,
}


def build_search_provider(
    *,
    name: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> SearchProvider | None:
    provider_cls = SEARCH_PROVIDERS.get(name.strip().lower())
    if provider_cls is None:
        return None
    if provider_cls is SearxngProvider:
        if not base_url:
            return None
        return SearxngProvider(base_url)
    if not api_key:
        return None
    return provider_cls(api_key)

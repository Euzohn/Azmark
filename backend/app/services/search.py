"""Resolve the user's SearchProvider (spec #37, #66).

Priority: global configuration (deployment env) -> the user's encrypted keys.
Never raises; returns None when no provider is configured so callers can
degrade gracefully (spec #70).
"""

from app.core.config import settings
from app.providers.search import SearchProvider, build_search_provider


def resolve_search_provider(user_keys: dict[str, str]) -> SearchProvider | None:
    name = (settings.search_provider or "").strip().lower()
    if name:
        provider = build_search_provider(
            name=name,
            api_key=settings.search_api_key or user_keys.get(name),
            base_url=settings.searxng_base_url
            or (user_keys.get(name) if name == "searxng" else user_keys.get("searxng")),
        )
        if provider is not None:
            return provider

    for candidate in ("tavily", "brave"):
        if user_keys.get(candidate):
            return build_search_provider(name=candidate, api_key=user_keys[candidate])
    if user_keys.get("searxng"):
        return build_search_provider(name="searxng", base_url=user_keys["searxng"])
    return None

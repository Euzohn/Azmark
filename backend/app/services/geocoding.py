"""Address normalization and match sanity checks for the locate action.

Geocoders frequently rank a same-named street in another country first — there
is an "Outram Road" in Singapore, New Zealand and Canada. The route therefore
tries a couple of address variants and only accepts a candidate whose display
name agrees with the address's own country/city hint.
"""

from __future__ import annotations

import re

from app.providers.geocode import GeocodeResult

_LATIN = re.compile(r"[a-z]")
_POSTCODE = re.compile(r"^[0-9]{4,8}$")

# Common abbreviations that appear as the last address component.
_COUNTRY_ALIASES = {
    "us": "united states",
    "usa": "united states",
    "uk": "united kingdom",
    "uae": "united arab emirates",
    "sg": "singapore",
    "jp": "japan",
    "cn": "china",
    "hk": "hong kong",
    "tw": "taiwan",
    "kr": "south korea",
}


def _parts(address: str) -> list[str]:
    return [part.strip() for part in address.split(",") if part.strip()]


def _is_postcode(part: str) -> bool:
    return bool(_POSTCODE.fullmatch(part.replace(" ", "")))


def address_query_variants(address: str) -> list[str]:
    """The address as written, then with postcodes and duplicate parts removed.

    ``261 Outram Rd, Singapore, Singapore, 169057`` is a poor full-text query;
    ``261 Outram Rd, Singapore`` resolves far more reliably.
    """
    raw = " ".join(address.split())
    if not raw:
        return []

    variants = [raw]
    parts = _parts(raw)
    deduped: list[str] = []
    for part in parts:
        if _is_postcode(part):
            continue
        if deduped and part.lower() == deduped[-1].lower():
            continue
        deduped.append(part)

    if deduped and deduped != parts:
        variant = ", ".join(deduped)
        if variant not in variants:
            variants.append(variant)
    return variants


def country_hint(address: str) -> str | None:
    """Last single-word, non-postcode component — usually the country or city.

    Only Latin hints are returned: they are the ones we can reliably compare
    against a geocoder's display name.
    """
    for part in reversed(_parts(address)):
        if _is_postcode(part):
            continue
        tokens = part.split()
        if len(tokens) == 1 and len(tokens[0]) >= 3 and _LATIN.search(tokens[0].lower()):
            return tokens[0].lower()
        return None
    return None


def is_consistent(result: GeocodeResult, hint: str | None) -> bool:
    """Reject matches that clearly belong to a different country/city."""
    if not hint:
        return True

    text = (result.display_name or "").lower()
    expected = _COUNTRY_ALIASES.get(hint, hint)
    if hint in text or expected in text:
        return True
    # A localized (non-Latin) display name cannot be checked reliably.
    if text and not _LATIN.search(text):
        return True
    return False

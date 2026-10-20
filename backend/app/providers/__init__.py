"""Provider registry (spec #66). Add new Flight/Search providers here."""

from app.providers.aerodatabox import AeroDataBoxProvider
from app.providers.aviationstack import AviationStackProvider
from app.providers.base import FlightProvider
from app.providers.search import SEARCH_PROVIDERS
from app.providers.variflight import VariflightProvider

REGISTERED_PROVIDERS: dict[str, type[FlightProvider]] = {
    AeroDataBoxProvider.name: AeroDataBoxProvider,
    AviationStackProvider.name: AviationStackProvider,
    VariflightProvider.name: VariflightProvider,
}


def provider_names() -> tuple[str, ...]:
    return tuple(REGISTERED_PROVIDERS) + tuple(SEARCH_PROVIDERS)

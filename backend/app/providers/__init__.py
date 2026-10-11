"""Provider registry (spec #66). Add new FlightProviders here."""

from app.providers.aerodatabox import AeroDataBoxProvider
from app.providers.aviationstack import AviationStackProvider
from app.providers.base import FlightProvider

REGISTERED_PROVIDERS: dict[str, type[FlightProvider]] = {
    AeroDataBoxProvider.name: AeroDataBoxProvider,
    AviationStackProvider.name: AviationStackProvider,
}


def provider_names() -> tuple[str, ...]:
    return tuple(REGISTERED_PROVIDERS)

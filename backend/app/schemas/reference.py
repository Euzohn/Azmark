from pydantic import BaseModel, ConfigDict


class AirportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    iata: str
    icao: str | None = None
    name: str
    name_zh: str | None = None
    city: str | None = None
    city_zh: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None


class AirlineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    iata: str
    icao: str | None = None
    name: str
    name_zh: str | None = None
    country: str | None = None


class FlightNumberLookup(BaseModel):
    flight_number: str
    airline_code: str | None = None
    airline: AirlineRead | None = None

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.reference import AirlineRead, AirportRead, FlightNumberLookup
from app.services import reference

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/airports", response_model=list[AirportRead])
def search_airports(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=10, ge=1, le=25),
    _: User = Depends(get_current_user),
) -> list[AirportRead]:
    return reference.search_airports(q, limit=limit)


@router.get("/airlines", response_model=list[AirlineRead])
def search_airlines(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=10, ge=1, le=25),
    _: User = Depends(get_current_user),
) -> list[AirlineRead]:
    return reference.search_airlines(q, limit=limit)


@router.get("/flight-lookup", response_model=FlightNumberLookup)
def flight_lookup(
    number: str = Query(min_length=2, max_length=10),
    _: User = Depends(get_current_user),
) -> FlightNumberLookup:
    return reference.lookup_flight_number(number)


@router.get("/airlines/{iata}", response_model=AirlineRead)
def get_airline(
    iata: str,
    _: User = Depends(get_current_user),
) -> AirlineRead:
    result = reference.get_airline_by_iata(iata.upper())
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result


@router.get("/airports/{iata}", response_model=AirportRead)
def get_airport(
    iata: str,
    _: User = Depends(get_current_user),
) -> AirportRead:
    result = reference.get_airport_by_iata(iata.upper())
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result

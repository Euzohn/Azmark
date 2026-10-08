from fastapi import APIRouter, Depends, Query

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

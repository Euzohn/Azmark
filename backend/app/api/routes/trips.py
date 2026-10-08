import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_trip_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.trip import TripCreate, TripDetail, TripList, TripRead, TripUpdate
from app.services.audit import AuditService
from app.services.trip import TripNotFoundError, TripService

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_model=TripList)
def list_trips(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> TripList:
    items, total = service.list_trips(user_id=current_user.id, page=page, page_size=page_size)
    return TripList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
):
    trip = service.create_trip(user_id=current_user.id, payload=payload)
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip.id),
        meta={"trip_status": trip.status},
        request=request,
    )
    return trip


@router.get("/{trip_id}", response_model=TripDetail)
def get_trip(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> TripDetail:
    try:
        trip = service.get_trip(user_id=current_user.id, trip_id=trip_id)
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    flights = service.list_flights(user_id=current_user.id, trip_id=trip_id)
    return TripDetail.model_validate(trip, from_attributes=True).model_copy(
        update={"flights": flights}
    )


@router.patch("/{trip_id}", response_model=TripRead)
def update_trip(
    trip_id: uuid.UUID,
    payload: TripUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        trip = service.update_trip(user_id=current_user.id, trip_id=trip_id, payload=payload)
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_trip(user_id=current_user.id, trip_id=trip_id)
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip_id),
        request=request,
    )

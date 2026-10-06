import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_flight_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.transport import FlightCreate, FlightList, FlightRead, FlightUpdate
from app.services.audit import AuditService
from app.services.transport import FlightService, RecordNotFoundError

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=FlightList)
def list_flights(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
) -> FlightList:
    items, total = service.list_flights(
        user_id=current_user.id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return FlightList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=FlightRead, status_code=status.HTTP_201_CREATED)
def create_flight(
    payload: FlightCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
    audit: AuditService = Depends(get_audit_service),
):
    record = service.create_flight(user_id=current_user.id, payload=payload)
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="flight",
        resource_id=str(record.id),
        meta={"transport_type": "flight"},
        request=request,
    )
    return record


@router.get("/{record_id}", response_model=FlightRead)
def get_flight(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
):
    try:
        return service.get_flight(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{record_id}", response_model=FlightRead)
def update_flight(
    record_id: uuid.UUID,
    payload: FlightUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        record = service.update_flight(
            user_id=current_user.id, record_id=record_id, payload=payload
        )
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="flight",
        resource_id=str(record.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flight(
    record_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_flight(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="flight",
        resource_id=str(record_id),
        request=request,
    )

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_attachment_service,
    get_audit_service,
    get_current_user,
    get_hotel_service,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.hotel import HotelCreate, HotelList, HotelRead, HotelUpdate
from app.services.attachment import AttachmentService
from app.services.audit import AuditService
from app.services.hotel import (
    DuplicateHotelError,
    HotelNotFoundError,
    HotelService,
    HotelTripAssignmentError,
)

router = APIRouter(prefix="/hotels", tags=["hotels"])

HotelSort = Literal["newest", "oldest", "check_out", "created"]


@router.get("", response_model=HotelList)
def list_hotels(
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    trip_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: HotelSort = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: HotelService = Depends(get_hotel_service),
) -> HotelList:
    items, total = service.list_hotels(
        user_id=current_user.id,
        search=search,
        status=status_filter,
        trip_id=trip_id,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return HotelList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=HotelRead, status_code=status.HTTP_201_CREATED)
def create_hotel(
    payload: HotelCreate,
    request: Request,
    force: bool = Query(False, description="Bypass duplicate check (spec #41)"),
    current_user: User = Depends(get_current_user),
    service: HotelService = Depends(get_hotel_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        hotel = service.create_hotel(user_id=current_user.id, payload=payload, force=force)
    except HotelTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except DuplicateHotelError as exc:
        existing = exc.existing_hotel
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate hotel",
                "existing_record": {
                    "id": str(existing.id),
                    "hotel": existing.hotel,
                    "check_in": existing.check_in.isoformat() if existing.check_in else None,
                    "check_out": existing.check_out.isoformat() if existing.check_out else None,
                    "address": existing.address,
                },
            },
        ) from None
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="hotel",
        resource_id=str(hotel.id),
        meta={"hotel": hotel.hotel},
        request=request,
    )
    return hotel


@router.get("/{hotel_id}", response_model=HotelRead)
def get_hotel(
    hotel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: HotelService = Depends(get_hotel_service),
):
    try:
        return service.get_hotel(user_id=current_user.id, hotel_id=hotel_id)
    except HotelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{hotel_id}", response_model=HotelRead)
def update_hotel(
    hotel_id: uuid.UUID,
    payload: HotelUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: HotelService = Depends(get_hotel_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        hotel = service.update_hotel(user_id=current_user.id, hotel_id=hotel_id, payload=payload)
    except HotelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="hotel",
        resource_id=str(hotel.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return hotel


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hotel(
    hotel_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: HotelService = Depends(get_hotel_service),
    attachments: AttachmentService = Depends(get_attachment_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.get_hotel(user_id=current_user.id, hotel_id=hotel_id)
    except HotelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    attachments.delete_for_resource(
        user_id=current_user.id, resource_type="hotel", resource_id=hotel_id
    )
    try:
        service.delete_hotel(user_id=current_user.id, hotel_id=hotel_id)
    except HotelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="hotel",
        resource_id=str(hotel_id),
        request=request,
    )

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
from app.providers.geocode import GeocodeProvider, GeocodeUnavailableError
from app.schemas.hotel import HotelCreate, HotelList, HotelRead, HotelUpdate
from app.schemas.status import RecordStatus
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
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
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


@router.post("/{hotel_id}/geocode", response_model=HotelRead)
async def geocode_hotel(
    hotel_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: HotelService = Depends(get_hotel_service),
    audit: AuditService = Depends(get_audit_service),
):
    """Geocode the stay's address (or name) and store the coordinates (spec #10).

    Explicit user action only: the public geocoders are rate-limited, so this
    never runs inside list/create flows. The address is tried first, then the
    hotel name (a bare "Marina Bay Sands" often resolves when the address is
    incomplete). "No match" is a 404; an unreachable service is a 503 so the UI
    does not blame the user's address for a network problem.
    """
    try:
        hotel = service.get_hotel(user_id=current_user.id, hotel_id=hotel_id)
    except HotelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None

    queries: list[str] = []
    for candidate in (hotel.address or "", hotel.hotel or ""):
        value = candidate.strip()
        if value and value not in queries:
            queries.append(value)

    provider = GeocodeProvider(language=current_user.locale)
    result = None
    try:
        for query in queries:
            result = await provider.search(query)
            if result is not None:
                break
    except GeocodeUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoder unavailable",
        ) from None

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No geocode result")
    hotel = service.set_coordinates(
        user_id=current_user.id, hotel_id=hotel_id, lat=result.lat, lon=result.lon
    )
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="hotel",
        resource_id=str(hotel.id),
        meta={"geocoded": True, "provider": result.provider or provider.name},
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

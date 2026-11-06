import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_trip_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.trip import (
    TripCreate,
    TripDetail,
    TripItemCreate,
    TripItemOrder,
    TripItemRead,
    TripItemUpdate,
    TripList,
    TripRead,
    TripUpdate,
)
from app.services.audit import AuditService
from app.services.idempotency import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyResultGoneError,
)
from app.services.trip import (
    InvalidTripItemTypeError,
    InvalidTripOrderError,
    TimelineRepairRequiredError,
    TripItemNotFoundError,
    TripNotFoundError,
    TripService,
)

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
    items = service.list_items(user_id=current_user.id, trip_id=trip_id)
    records = [item.record for item in items if item.record is not None]
    expenses = service.list_expenses(user_id=current_user.id, trip_id=trip_id)
    summary = service.expense_summary(user_id=current_user.id, trip_id=trip_id)
    notes = service.list_notes(user_id=current_user.id, trip_id=trip_id)
    attachments = service.list_attachments(user_id=current_user.id, trip_id=trip_id)
    return TripDetail.model_validate(trip, from_attributes=True).model_copy(
        update={
            "records": records,
            "items": items,
            "expenses": expenses,
            "expense_summary": summary,
            "notes": notes,
            "attachments": attachments,
        }
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


@router.put("/{trip_id}/items/order", status_code=status.HTTP_204_NO_CONTENT)
def reorder_trip_items(
    trip_id: uuid.UUID,
    payload: TripItemOrder,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.reorder_items(user_id=current_user.id, trip_id=trip_id, item_ids=payload.item_ids)
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except TimelineRepairRequiredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Timeline repair required before reordering",
        ) from None
    except InvalidTripOrderError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Invalid item order"
        ) from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip_id),
        meta={"reordered_items": len(payload.item_ids)},
        request=request,
    )


@router.post("/{trip_id}/timeline/repair")
def repair_timeline(
    trip_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, int]:
    """Rebuild missing/stale timeline projections explicitly (never on read)."""
    try:
        counts = service.repair_timeline(user_id=current_user.id, trip_id=trip_id)
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip_id),
        meta={"timeline_repair": counts},
        request=request,
    )
    return counts


@router.patch("/{trip_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_trip_item(
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: TripItemUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.update_item(
            user_id=current_user.id,
            trip_id=trip_id,
            item_id=item_id,
            payload=payload,
        )
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except TripItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except TimelineRepairRequiredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Timeline repair required before reordering",
        ) from None
    except InvalidTripOrderError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Invalid item position"
        ) from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip_id),
        meta={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )


@router.post("/{trip_id}/items", response_model=TripItemRead, status_code=status.HTTP_201_CREATED)
def add_trip_item(
    trip_id: uuid.UUID,
    payload: TripItemCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=120),
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
) -> TripItemRead:
    """Create a visit Activity from a place (legacy add-item facade, spec #9.1)."""
    try:
        item, replayed = service.add_item(
            user_id=current_user.id,
            trip_id=trip_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except TripItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        ) from None
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reused with a different request",
        ) from None
    except IdempotencyInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Request is still in progress"
        ) from None
    except IdempotencyResultGoneError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The result of this key was deleted",
        ) from None
    except InvalidTripItemTypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only places can be added"
        ) from None
    if not replayed:
        audit.log(
            action=AuditAction.UPDATE_RECORD,
            user_id=current_user.id,
            resource_type="trip",
            resource_id=str(trip_id),
            meta={"added_item": str(item.id), "item_type": item.item_type},
            request=request,
        )
    return item


@router.delete("/{trip_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip_item(
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Detach a source record from the trip without deleting the record."""
    try:
        service.remove_item(user_id=current_user.id, trip_id=trip_id, item_id=item_id)
    except TripNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except TripItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except InvalidTripItemTypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only place items can be removed here",
        ) from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="trip",
        resource_id=str(trip_id),
        meta={"removed_item": str(item_id)},
        request=request,
    )


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

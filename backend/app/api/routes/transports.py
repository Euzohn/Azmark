import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_attachment_service,
    get_audit_service,
    get_current_user,
    get_transport_service,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.transport import (
    OtherTransportCreate,
    OtherTransportList,
    OtherTransportRead,
    OtherTransportUpdate,
)
from app.services.attachment import AttachmentService
from app.services.audit import AuditService
from app.services.transport import DuplicateRecordError, OtherTransportService, RecordNotFoundError

router = APIRouter(prefix="/other-transports", tags=["other-transports"])


@router.get("", response_model=OtherTransportList)
def list_other_transports(
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    trip_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: OtherTransportService = Depends(get_transport_service),
) -> OtherTransportList:
    items, total = service.list_records(
        user_id=current_user.id,
        search=search,
        status=status_filter,
        trip_id=trip_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return OtherTransportList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=OtherTransportRead, status_code=status.HTTP_201_CREATED)
def create_other_transport(
    payload: OtherTransportCreate,
    request: Request,
    force: bool = Query(False, description="Bypass duplicate check (spec #41)"),
    current_user: User = Depends(get_current_user),
    service: OtherTransportService = Depends(get_transport_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        record = service.create_record(
            user_id=current_user.id, payload=payload, force=force
        )
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except DuplicateRecordError as exc:
        existing = exc.existing_record
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate record",
                "existing_record": {
                    "id": str(existing.id),
                    "service_number": existing.service_number,
                    "carrier": existing.carrier,
                    "departure_time": (
                        existing.departure_time.isoformat()
                        if existing.departure_time
                        else None
                    ),
                    "departure_timezone": existing.departure_timezone,
                    "origin": existing.origin,
                    "destination": existing.destination,
                },
            },
        ) from None
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="transport",
        resource_id=str(record.id),
        meta={"transport_type": "other"},
        request=request,
    )
    return record


@router.get("/{record_id}", response_model=OtherTransportRead)
def get_other_transport(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OtherTransportService = Depends(get_transport_service),
):
    try:
        return service.get_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{record_id}", response_model=OtherTransportRead)
def update_other_transport(
    record_id: uuid.UUID,
    payload: OtherTransportUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: OtherTransportService = Depends(get_transport_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        record = service.update_record(
            user_id=current_user.id, record_id=record_id, payload=payload
        )
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="transport",
        resource_id=str(record.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_other_transport(
    record_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: OtherTransportService = Depends(get_transport_service),
    attachments: AttachmentService = Depends(get_attachment_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.get_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    attachments.delete_for_resource(
        user_id=current_user.id, resource_type="transport", resource_id=record_id
    )
    try:
        service.delete_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="transport",
        resource_id=str(record_id),
        request=request,
    )

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_attachment_service,
    get_audit_service,
    get_current_user,
    get_flight_enrichment_service,
    get_flight_service,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.flight_lookup import (
    FlightLookupRequest,
    FlightLookupResponse,
    LookupAllResponse,
)
from app.schemas.transport import FlightCreate, FlightList, FlightRead, FlightUpdate
from app.services.attachment import AttachmentService
from app.services.audit import AuditService
from app.services.flight_enrichment import FlightEnrichmentService, ProviderNotFoundError
from app.services.transport import DuplicateRecordError, FlightService, RecordNotFoundError

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=FlightList)
def list_flights(
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    cabin_class: str | None = None,
    trip_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
) -> FlightList:
    items, total = service.list_records(
        user_id=current_user.id,
        search=search,
        status=status_filter,
        cabin_class=cabin_class,
        trip_id=trip_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return FlightList(items=items, total=total, page=page, page_size=page_size)


@router.post("/lookup", response_model=FlightLookupResponse)
async def lookup_flight(
    payload: FlightLookupRequest,
    current_user: User = Depends(get_current_user),
    enrichment: FlightEnrichmentService = Depends(get_flight_enrichment_service),
) -> FlightLookupResponse:
    try:
        return await enrichment.lookup(
            user_id=current_user.id,
            flight_number=payload.flight_number,
            date=payload.date or date.today(),
            provider=payload.provider,
        )
    except ProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown provider"
        ) from None


@router.post("/lookup-all", response_model=LookupAllResponse)
async def lookup_flight_all(
    payload: FlightLookupRequest,
    current_user: User = Depends(get_current_user),
    enrichment: FlightEnrichmentService = Depends(get_flight_enrichment_service),
) -> LookupAllResponse:
    results = await enrichment.lookup_all(
        user_id=current_user.id,
        flight_number=payload.flight_number,
        date=payload.date or date.today(),
    )
    return LookupAllResponse(
        flight_number=payload.flight_number,
        results=results,
    )


@router.post("", response_model=FlightRead, status_code=status.HTTP_201_CREATED)
def create_flight(
    payload: FlightCreate,
    request: Request,
    force: bool = Query(False, description="Bypass duplicate check (spec #41)"),
    current_user: User = Depends(get_current_user),
    service: FlightService = Depends(get_flight_service),
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
        return service.get_record(user_id=current_user.id, record_id=record_id)
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
        record = service.update_record(
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
    attachments: AttachmentService = Depends(get_attachment_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.get_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    attachments.delete_for_resource(
        user_id=current_user.id, resource_type="flight", resource_id=record_id
    )
    try:
        service.delete_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="flight",
        resource_id=str(record_id),
        request=request,
    )

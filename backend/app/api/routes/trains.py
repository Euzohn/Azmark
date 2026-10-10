import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_train_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.transport import TrainCreate, TrainList, TrainRead, TrainUpdate
from app.services.audit import AuditService
from app.services.transport import RecordNotFoundError, TrainService

router = APIRouter(prefix="/trains", tags=["trains"])


@router.get("", response_model=TrainList)
def list_trains(
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    cabin_class: str | None = None,
    trip_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: TrainService = Depends(get_train_service),
) -> TrainList:
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
    return TrainList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TrainRead, status_code=status.HTTP_201_CREATED)
def create_train(
    payload: TrainCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TrainService = Depends(get_train_service),
    audit: AuditService = Depends(get_audit_service),
):
    record = service.create_record(user_id=current_user.id, payload=payload)
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="train",
        resource_id=str(record.id),
        meta={"transport_type": "train"},
        request=request,
    )
    return record


@router.get("/{record_id}", response_model=TrainRead)
def get_train(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TrainService = Depends(get_train_service),
):
    try:
        return service.get_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{record_id}", response_model=TrainRead)
def update_train(
    record_id: uuid.UUID,
    payload: TrainUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TrainService = Depends(get_train_service),
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
        resource_type="train",
        resource_id=str(record.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_train(
    record_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TrainService = Depends(get_train_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_record(user_id=current_user.id, record_id=record_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="train",
        resource_id=str(record_id),
        request=request,
    )

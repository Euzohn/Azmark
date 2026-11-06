import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.deps import (
    get_activity_service,
    get_audit_service,
    get_current_user,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.activity import (
    ActivityCreate,
    ActivityList,
    ActivityRead,
    ActivityType,
    ActivityUpdate,
)
from app.services.activity import (
    ActivityNotFoundError,
    ActivityPlaceAssignmentError,
    ActivityService,
    ActivityTripAssignmentError,
    InvalidActivityWindowError,
)
from app.services.audit import AuditService
from app.services.idempotency import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyResultGoneError,
)

router = APIRouter(prefix="/activities", tags=["activities"])

ActivitySort = Literal["newest", "oldest", "created"]


@router.get("", response_model=ActivityList)
def list_activities(
    search: str | None = None,
    type_filter: ActivityType | None = Query(default=None, alias="type"),
    trip_id: uuid.UUID | None = None,
    place_id: uuid.UUID | None = None,
    sort: ActivitySort = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
) -> ActivityList:
    items, total = service.list_activities(
        user_id=current_user.id,
        search=search,
        type=type_filter,
        trip_id=trip_id,
        place_id=place_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return ActivityList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=120),
    current_user: User = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
    audit: AuditService = Depends(get_audit_service),
) -> ActivityRead:
    try:
        activity, replayed = service.create_activity_idempotent(
            user_id=current_user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except ActivityTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except ActivityPlaceAssignmentError:
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
    if not replayed:
        audit.log(
            action=AuditAction.CREATE_RECORD,
            user_id=current_user.id,
            resource_type="activity",
            resource_id=str(activity.id),
            meta={"name": activity.name},
            request=request,
        )
    return activity


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(
    activity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
) -> ActivityRead:
    try:
        return service.get_activity(user_id=current_user.id, activity_id=activity_id)
    except ActivityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: uuid.UUID,
    payload: ActivityUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
    audit: AuditService = Depends(get_audit_service),
) -> ActivityRead:
    try:
        activity = service.update_activity(
            user_id=current_user.id, activity_id=activity_id, payload=payload
        )
    except ActivityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except ActivityTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except ActivityPlaceAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        ) from None
    except InvalidActivityWindowError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid activity window"
        ) from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="activity",
        resource_id=str(activity.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_activity(user_id=current_user.id, activity_id=activity_id)
    except ActivityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="activity",
        resource_id=str(activity_id),
        request=request,
    )

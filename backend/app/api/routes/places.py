import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_audit_service,
    get_current_user,
    get_place_service,
)
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.place import PlaceCreate, PlaceList, PlaceRead, PlaceType, PlaceUpdate
from app.services.audit import AuditService
from app.services.place import PlaceNotFoundError, PlaceService

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=PlaceList)
def list_places(
    search: str | None = None,
    type_filter: PlaceType | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: PlaceService = Depends(get_place_service),
) -> PlaceList:
    items, total = service.list_places(
        user_id=current_user.id,
        search=search,
        type=type_filter,
        page=page,
        page_size=page_size,
    )
    return PlaceList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=PlaceRead, status_code=status.HTTP_201_CREATED)
def create_place(
    payload: PlaceCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: PlaceService = Depends(get_place_service),
    audit: AuditService = Depends(get_audit_service),
) -> PlaceRead:
    place = service.create_place(user_id=current_user.id, payload=payload, commit=False)
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="place",
        resource_id=str(place.id),
        meta={"name": place.name},
        request=request,
    )
    return place


@router.get("/{place_id}", response_model=PlaceRead)
def get_place(
    place_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PlaceService = Depends(get_place_service),
) -> PlaceRead:
    try:
        return service.get_place(user_id=current_user.id, place_id=place_id)
    except PlaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{place_id}", response_model=PlaceRead)
def update_place(
    place_id: uuid.UUID,
    payload: PlaceUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: PlaceService = Depends(get_place_service),
    audit: AuditService = Depends(get_audit_service),
) -> PlaceRead:
    try:
        place = service.update_place(
            user_id=current_user.id, place_id=place_id, payload=payload, commit=False
        )
    except PlaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="place",
        resource_id=str(place.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return place


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_place(
    place_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: PlaceService = Depends(get_place_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_place(user_id=current_user.id, place_id=place_id, commit=False)
    except PlaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="place",
        resource_id=str(place_id),
        request=request,
    )

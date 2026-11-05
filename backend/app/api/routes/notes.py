import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_audit_service, get_current_user, get_note_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.note import NoteCreate, NoteList, NoteRead, NoteUpdate
from app.services.audit import AuditService
from app.services.note import NoteNotFoundError, NoteService, NoteTripAssignmentError

router = APIRouter(prefix="/notes", tags=["notes"])

NoteSort = Literal["newest", "oldest", "updated", "title"]


@router.get("", response_model=NoteList)
def list_notes(
    search: str | None = None,
    trip_id: uuid.UUID | None = None,
    sort: NoteSort = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
) -> NoteList:
    items, total = service.list_notes(
        user_id=current_user.id,
        search=search,
        trip_id=trip_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return NoteList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        note = service.create_note(user_id=current_user.id, payload=payload)
    except NoteTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="note",
        resource_id=str(note.id),
        meta={"title": note.title},
        request=request,
    )
    return note


@router.get("/{note_id}", response_model=NoteRead)
def get_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
):
    try:
        return service.get_note(user_id=current_user.id, note_id=note_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        note = service.update_note(user_id=current_user.id, note_id=note_id, payload=payload)
    except NoteTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="note",
        resource_id=str(note.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete_note(user_id=current_user.id, note_id=note_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="note",
        resource_id=str(note_id),
        request=request,
    )

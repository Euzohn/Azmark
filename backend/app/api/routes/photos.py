"""Travel photos backed by S3-compatible storage (spec #20, #44, #57)."""

import uuid
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api.deps import get_audit_service, get_current_user, get_photo_service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.photo import PhotoList, PhotoRead, PhotoUpdate
from app.services.audit import AuditService
from app.services.photo import (
    EmptyPhotoError,
    InvalidPhotoError,
    PhotoNotFoundError,
    PhotoService,
    PhotoStorageUnavailableError,
    PhotoTooLargeError,
    PhotoTripAssignmentError,
    UnsupportedPhotoTypeError,
)

router = APIRouter(prefix="/photos", tags=["photos"])

PhotoSort = Literal["newest", "oldest", "uploaded"]
PhotoVariant = Literal["full", "thumb"]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _unsupported() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Only JPEG, PNG, WebP and GIF photos are supported; convert HEIC to JPEG",
    )


def _storage_down() -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage unavailable")


@router.post("", response_model=PhotoRead, status_code=status.HTTP_201_CREATED)
def upload_photo(
    request: Request,
    file: Annotated[UploadFile, File()],
    trip_id: Annotated[uuid.UUID | None, Form()] = None,
    utc_offset_minutes: Annotated[int | None, Form(ge=-840, le=840)] = None,
    current_user: User = Depends(get_current_user),
    service: PhotoService = Depends(get_photo_service),
    audit: AuditService = Depends(get_audit_service),
) -> PhotoRead:
    try:
        photo = service.upload(
            user_id=current_user.id,
            filename=file.filename,
            stream=file.file,
            trip_id=trip_id,
            utc_offset_minutes=utc_offset_minutes,
        )
    except PhotoTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except (UnsupportedPhotoTypeError, InvalidPhotoError):
        raise _unsupported() from None
    except PhotoTooLargeError:
        raise HTTPException(status_code=413, detail="Photo is too large") from None
    except EmptyPhotoError:
        raise HTTPException(status_code=422, detail="File is empty") from None
    except PhotoStorageUnavailableError:
        raise _storage_down() from None

    audit.log(
        action=AuditAction.CREATE_RECORD,
        user_id=current_user.id,
        resource_type="photo",
        resource_id=str(photo.id),
        meta={"mime_type": photo.mime_type},
        request=request,
    )
    return photo


@router.get("", response_model=PhotoList)
def list_photos(
    search: str | None = None,
    trip_id: uuid.UUID | None = None,
    sort: PhotoSort = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: PhotoService = Depends(get_photo_service),
) -> PhotoList:
    items, total = service.list_photos(
        user_id=current_user.id,
        search=search,
        trip_id=trip_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return PhotoList(items=items, total=total, page=page, page_size=page_size)


@router.get("/{photo_id}", response_model=PhotoRead)
def get_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PhotoService = Depends(get_photo_service),
) -> PhotoRead:
    try:
        return service.get_photo(user_id=current_user.id, photo_id=photo_id)
    except PhotoNotFoundError:
        raise _not_found() from None


@router.patch("/{photo_id}", response_model=PhotoRead)
def update_photo(
    photo_id: uuid.UUID,
    payload: PhotoUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: PhotoService = Depends(get_photo_service),
    audit: AuditService = Depends(get_audit_service),
) -> PhotoRead:
    try:
        photo = service.update_photo(
            user_id=current_user.id, photo_id=photo_id, payload=payload, commit=False
        )
    except PhotoTripAssignmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        ) from None
    except PhotoNotFoundError:
        raise _not_found() from None
    audit.log(
        action=AuditAction.UPDATE_RECORD,
        user_id=current_user.id,
        resource_type="photo",
        resource_id=str(photo.id),
        meta={"changed_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return photo


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    photo_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: PhotoService = Depends(get_photo_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        objects = service.delete_photo(user_id=current_user.id, photo_id=photo_id, commit=False)
    except PhotoNotFoundError:
        raise _not_found() from None
    audit.log(
        action=AuditAction.DELETE_RECORD,
        user_id=current_user.id,
        resource_type="photo",
        resource_id=str(photo_id),
        request=request,
    )
    # Blobs go after the transaction commits, so a failed delete keeps both
    # the row and the objects consistent.
    service.cleanup_staged_objects(objects)


@router.get("/{photo_id}/image")
def get_photo_image(
    photo_id: uuid.UUID,
    variant: PhotoVariant = "full",
    current_user: User = Depends(get_current_user),
    service: PhotoService = Depends(get_photo_service),
) -> Response:
    try:
        photo, data, mime = service.image(
            user_id=current_user.id, photo_id=photo_id, variant=variant
        )
    except PhotoNotFoundError:
        raise _not_found() from None
    except PhotoStorageUnavailableError:
        raise _storage_down() from None

    filename = quote(photo.filename, safe="")
    return Response(
        content=data,
        media_type=mime,
        headers={
            # Inline is safe here: the bytes were decoded as a raster image at
            # upload time, the stored MIME is image-only, and nosniff stops the
            # browser from reinterpreting them as anything executable.
            "Content-Disposition": f"inline; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, max-age=3600",
        },
    )

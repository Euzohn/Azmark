"""File attachments backed by S3-compatible storage (spec #24, #44, #57)."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api.deps import get_attachment_service, get_audit_service, get_current_user
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.attachment import AttachmentList, AttachmentRead
from app.services.attachment import (
    AttachmentNotFoundError,
    AttachmentService,
    EmptyFileError,
    FileTooLargeError,
    ResourceNotFoundError,
    StorageUnavailableError,
    UnsupportedFileTypeError,
    UnsupportedResourceTypeError,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    request: Request,
    file: Annotated[UploadFile, File()],
    resource_type: Annotated[str, Form()],
    resource_id: Annotated[uuid.UUID, Form()],
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
    audit: AuditService = Depends(get_audit_service),
) -> AttachmentRead:
    try:
        attachment = service.upload(
            user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_id,
            filename=file.filename,
            content_type=file.content_type,
            stream=file.file,
        )
    except UnsupportedResourceTypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported resource type"
        ) from None
    except ResourceNotFoundError:
        raise _not_found() from None
    except UnsupportedFileTypeError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only images and PDF files are supported",
        ) from None
    except FileTooLargeError:
        raise HTTPException(status_code=413, detail="File is too large") from None
    except EmptyFileError:
        raise HTTPException(status_code=422, detail="File is empty") from None
    except StorageUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage unavailable"
        ) from None

    audit.log(
        action=AuditAction.UPLOAD_ATTACHMENT,
        user_id=current_user.id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        meta={"attachment_id": str(attachment.id), "mime_type": attachment.mime_type},
        request=request,
    )
    return attachment


@router.get("", response_model=AttachmentList)
def list_attachments(
    resource_type: str,
    resource_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
) -> AttachmentList:
    try:
        items = service.list(
            user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except UnsupportedResourceTypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported resource type"
        ) from None
    except ResourceNotFoundError:
        raise _not_found() from None
    return AttachmentList(items=items, total=len(items))


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
) -> Response:
    try:
        attachment, data = service.download(user_id=current_user.id, attachment_id=attachment_id)
    except AttachmentNotFoundError:
        raise _not_found() from None
    except StorageUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage unavailable"
        ) from None

    filename = quote(attachment.filename, safe="")
    return Response(
        content=data,
        media_type=attachment.mime_type,
        headers={
            # Always download (never render) and never let browsers sniff a
            # different type from the uploaded bytes.
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AttachmentService = Depends(get_attachment_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    try:
        service.delete(user_id=current_user.id, attachment_id=attachment_id)
    except AttachmentNotFoundError:
        raise _not_found() from None
    except StorageUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage unavailable"
        ) from None
    audit.log(
        action=AuditAction.DELETE_ATTACHMENT,
        user_id=current_user.id,
        resource_type="attachment",
        resource_id=str(attachment_id),
        request=request,
    )

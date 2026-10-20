import logging
import mimetypes
import uuid
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.repositories.attachment import AttachmentRepository
from app.repositories.transport import TransportRepository
from app.services.storage import (
    StorageError,
    StorageObjectNotFound,
    StorageProvider,
)

logger = logging.getLogger(__name__)

# API resource type -> TransportRecord.type
ALLOWED_RESOURCE_TYPES: dict[str, str] = {
    "flight": "flight",
    "train": "train",
    "transport": "other",
}

# Boarding passes, tickets and receipts are images or PDFs (spec #59). SVG and
# HTML are deliberately excluded because they can execute when rendered.
ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heic",
        "image/heif",
        "image/tiff",
    }
)


class AttachmentError(Exception):
    pass


class AttachmentNotFoundError(AttachmentError):
    pass


class ResourceNotFoundError(AttachmentError):
    pass


class UnsupportedResourceTypeError(AttachmentError):
    pass


class UnsupportedFileTypeError(AttachmentError):
    pass


class FileTooLargeError(AttachmentError):
    pass


class EmptyFileError(AttachmentError):
    pass


class StorageUnavailableError(AttachmentError):
    pass


def _clean_filename(filename: str | None) -> str:
    name = (filename or "attachment").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if char.isprintable()).strip()
    return name[:255] or "attachment"


def _normalize_mime(filename: str, content_type: str | None) -> str:
    mime = (content_type or "").split(";")[0].strip().lower()
    if not mime or mime == "application/octet-stream":
        mime = mimetypes.guess_type(filename)[0] or ""
    return mime


class AttachmentService:
    """Upload/list/download/delete user files (spec #24, #44, #57)."""

    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self.repo = AttachmentRepository(db)
        self.records = TransportRepository(db)
        self.storage = storage

    def _ensure_resource(
        self,
        *,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> None:
        expected_type = ALLOWED_RESOURCE_TYPES.get(resource_type)
        if expected_type is None:
            raise UnsupportedResourceTypeError
        record = self.records.get(user_id=user_id, record_id=resource_id)
        if record is None or record.type != expected_type:
            raise ResourceNotFoundError

    def list(
        self,
        *,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> list[Attachment]:
        self._ensure_resource(user_id=user_id, resource_type=resource_type, resource_id=resource_id)
        return self.repo.list_for_resource(
            user_id=user_id, resource_type=resource_type, resource_id=resource_id
        )

    def upload(
        self,
        *,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
    ) -> Attachment:
        self._ensure_resource(user_id=user_id, resource_type=resource_type, resource_id=resource_id)

        clean_name = _clean_filename(filename)
        mime = _normalize_mime(clean_name, content_type)
        if mime not in ALLOWED_MIME_TYPES:
            raise UnsupportedFileTypeError

        max_bytes = settings.max_attachment_bytes
        data = stream.read(max_bytes + 1)
        if not data:
            raise EmptyFileError
        if len(data) > max_bytes:
            raise FileTooLargeError

        attachment_id = uuid.uuid4()
        storage_key = f"users/{user_id}/attachments/{attachment_id}"
        try:
            self.storage.put(key=storage_key, data=data, content_type=mime)
        except StorageError as exc:
            raise StorageUnavailableError from exc

        attachment = Attachment(
            id=attachment_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            storage_key=storage_key,
            filename=clean_name,
            mime_type=mime,
            size=len(data),
        )
        try:
            return self.repo.create(attachment)
        except Exception:
            # Never leave an object behind if the metadata insert fails.
            self._delete_object_best_effort(storage_key, attachment_id)
            raise

    def download(self, *, user_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[Attachment, bytes]:
        attachment = self.repo.get(user_id=user_id, attachment_id=attachment_id)
        if attachment is None:
            raise AttachmentNotFoundError
        try:
            data = self.storage.get(key=attachment.storage_key)
        except StorageObjectNotFound as exc:
            raise AttachmentNotFoundError from exc
        except StorageError as exc:
            raise StorageUnavailableError from exc
        return attachment, data

    def delete(self, *, user_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
        attachment = self.repo.get(user_id=user_id, attachment_id=attachment_id)
        if attachment is None:
            raise AttachmentNotFoundError
        try:
            self.storage.delete(key=attachment.storage_key)
        except StorageError as exc:
            raise StorageUnavailableError from exc
        self.repo.delete(attachment)

    def delete_for_resource(
        self,
        *,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> None:
        """Cascade cleanup when a record is deleted."""
        attachments = self.repo.list_for_resource(
            user_id=user_id, resource_type=resource_type, resource_id=resource_id
        )
        for attachment in attachments:
            self._delete_object_best_effort(attachment.storage_key, attachment.id)
        if attachments:
            self.repo.delete_many(attachments)

    def delete_for_user(self, *, user_id: uuid.UUID) -> None:
        """Cascade cleanup before deleting an account (spec #48)."""
        attachments = self.repo.list_for_user(user_id=user_id)
        for attachment in attachments:
            self._delete_object_best_effort(attachment.storage_key, attachment.id)
        if attachments:
            self.repo.delete_many(attachments)

    def _delete_object_best_effort(self, storage_key: str, attachment_id: uuid.UUID) -> None:
        try:
            self.storage.delete(key=storage_key)
        except StorageError:
            # Do not block record/account deletion on an unavailable backend;
            # log only the opaque id, never the user's filename or key.
            logger.warning("Could not delete attachment object %s", attachment_id)

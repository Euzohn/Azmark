"""Per-user object-storage quota (spec #44, #57).

Usage is the sum of stored binaries — attachments and photo originals. Both
upload paths hold the per-user write lock before enforcing, so concurrent
uploads cannot overshoot the cap. Photo thumbnails are derived objects
(~30 KB each) and are deliberately not counted; deleting a file frees quota
because usage is computed from the rows themselves.

A quota of 0 means unlimited. Admins are exempt from enforcement: they are the
ones handing out quotas and must never lock themselves out.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.photo import Photo
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole
from app.services.system_setting import SETTINGS_ROW_ID


class StorageQuotaExceededError(Exception):
    """The upload would push the user past their quota (mapped to HTTP 507)."""


def used_bytes(db: Session, user_id: uuid.UUID) -> int:
    """Total bytes the user currently occupies (attachments + photo originals)."""
    attachment_bytes = db.scalar(
        select(func.coalesce(func.sum(Attachment.size), 0)).where(Attachment.user_id == user_id)
    )
    photo_bytes = db.scalar(
        select(func.coalesce(func.sum(Photo.size), 0)).where(Photo.user_id == user_id)
    )
    return int(attachment_bytes or 0) + int(photo_bytes or 0)


def default_quota_bytes(db: Session) -> int:
    """Instance default; 0 = unlimited.

    Read-only on purpose: the upload paths call this while holding the user
    write lock, and ``SystemSettingsService.get_or_create`` would commit.
    """
    row = db.get(SystemSetting, SETTINGS_ROW_ID)
    return int(row.default_storage_quota_bytes) if row is not None else 0


def effective_quota_bytes(db: Session, user: User) -> int:
    """Per-user override wins; otherwise the instance default; 0 = unlimited."""
    if user.storage_quota_bytes is not None:
        return int(user.storage_quota_bytes)
    return default_quota_bytes(db)


def enforce_storage_quota(db: Session, *, user_id: uuid.UUID, incoming_bytes: int) -> None:
    """Raise before the binary is written; call inside ``lock_user_writes``."""
    user = db.get(User, user_id)
    if user is None or user.role == UserRole.ADMIN:
        return
    quota = effective_quota_bytes(db, user)
    if quota <= 0:
        return
    if used_bytes(db, user_id) + incoming_bytes > quota:
        raise StorageQuotaExceededError

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_ip
from app.models.audit_log import AuditLog


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


class AuditService:
    """Records important actions (spec #47). Never log sensitive raw values (#45, #96)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        meta: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            meta=meta,
            ip_hash=hash_ip(client_ip(request)) if request is not None else None,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Cross-user audit trail for admins (spec #5, #47)."""
        conditions = []
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)

        count_stmt = select(func.count()).select_from(AuditLog)
        stmt = select(AuditLog)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            stmt = stmt.where(condition)

        total = self.db.scalar(count_stmt)
        stmt = (
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def list_for_user(
        self, *, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> tuple[list[AuditLog], int]:
        total = self.db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id)
        )
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

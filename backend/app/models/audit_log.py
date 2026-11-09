import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class AuditLog(Base):
    """Audit trail (spec #47). Never store sensitive raw values (spec #45, #96)."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    # Correlation context (spec #47). request_id groups every audit row that one
    # HTTP request produced; user_agent is a sanitised, truncated client hint.
    user_agent: Mapped[str | None] = mapped_column(String(200))
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class AuditAction:
    REGISTER = "register"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    USERNAME_CHANGE = "username_change"
    ACCOUNT_CHANGE = "account_change"
    ACCOUNT_DELETE = "account_delete"
    CREATE_RECORD = "create_record"
    UPDATE_RECORD = "update_record"
    DELETE_RECORD = "delete_record"
    IMPORT = "import"
    EXPORT = "export"
    UPLOAD_ATTACHMENT = "upload_attachment"
    DELETE_ATTACHMENT = "delete_attachment"
    AI_ACTION = "ai_action"
    ADMIN_BOOTSTRAP = "admin_bootstrap"
    ADMIN_UPDATE_USER = "admin_update_user"
    CREATE_ACCESS_TOKEN = "create_access_token"
    REVOKE_ACCESS_TOKEN = "revoke_access_token"
    DELETE_ACCESS_TOKEN = "delete_access_token"
    CREATE_PENDING_ACTION = "create_pending_action"
    CONFIRM_PENDING_ACTION = "confirm_pending_action"
    REJECT_PENDING_ACTION = "reject_pending_action"

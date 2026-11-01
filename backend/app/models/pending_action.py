import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class PendingActionStatus:
    """Lifecycle of an action proposed by an external agent (spec #69, #85)."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"

    ALL = (PENDING, CONFIRMED, REJECTED, FAILED, EXPIRED)


class PendingActionKind:
    """Only non-destructive writes are ever proposed by MCP (spec #69)."""

    CREATE = "create"
    UPDATE = "update"

    ALL = (CREATE, UPDATE)


class PendingAction(Base):
    """A write an agent asked for, waiting for a human to approve it.

    The MCP transport is driven by a model, so a tool call cannot be treated as
    the user's consent: a malicious prompt could ask the agent to delete or
    rewrite data, and the agent would happily "confirm" itself. Proposals are
    therefore persisted here and executed only through a browser session
    (``GET/POST /pending-actions`` rejects personal access tokens).

    ``token_name`` is a snapshot: the row stays readable after the token that
    created it is deleted.
    """

    __tablename__ = "pending_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("personal_access_tokens.id", ondelete="SET NULL"), index=True
    )
    token_name: Mapped[str | None] = mapped_column(String(100))

    action: Mapped[str] = mapped_column(String(20), nullable=False)
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Human-readable one-liner shown in the approval inbox.
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=PendingActionStatus.PENDING, nullable=False, index=True
    )
    # id + type of the record that was actually written, once confirmed.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

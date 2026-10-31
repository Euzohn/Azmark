import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class TokenScope:
    """Permission tiers for personal access tokens (spec #33, #85).

    ``read`` is the default: external agents can query the traveller's data but
    cannot change it. ``write`` unlocks mutating endpoints; destructive actions
    still go through the proposal/confirmation flow (spec #69).
    """

    READ = "read"
    WRITE = "write"

    ALL = (READ, WRITE)


class PersonalAccessToken(Base):
    """Long-lived credential for agents, scripts and CLIs (spec #85).

    Only the SHA-256 digest of the secret is persisted; the plaintext token is
    shown once at creation and never logged (spec #45, #75). Rows are scoped to
    a user and are revoked or deleted explicitly, so a leaked token can be cut
    off immediately without affecting the web session.
    """

    __tablename__ = "personal_access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # First characters of the secret, kept only so the UI can tell tokens apart.
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(10), default=TokenScope.READ, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

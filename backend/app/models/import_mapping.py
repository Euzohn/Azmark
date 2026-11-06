import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class ImportBundleMapping(Base):
    """Exported-id → target-id map for idempotent v2 bundle imports (§10.6).

    Scoped by user and bundle so two users importing the same file never share
    rows, and importing the same bundle twice reuses the first result.
    """

    __tablename__ = "import_bundle_mappings"
    __table_args__ = (
        Index("ix_import_mappings_user_bundle", "user_id", "bundle_id"),
        UniqueConstraint(
            "user_id",
            "bundle_id",
            "entity_type",
            "exported_id",
            name="uq_import_mappings_user_bundle_entity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    exported_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # Sha256 of the exported entity payload. Re-importing the same bundle with
    # changed content under the same identifier is a conflict, not an update.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class DataSource(Base):
    """Provenance for external data (spec #22, #37).

    Every external lookup/import can leave a row describing where the data
    came from. Rows are always scoped to one user (spec #57); ``meta`` maps to
    the SQL column named ``metadata`` (the attribute cannot use that name
    because it would shadow SQLAlchemy's declarative ``Base.metadata``).
    """

    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str | None] = mapped_column(String(40))

    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)

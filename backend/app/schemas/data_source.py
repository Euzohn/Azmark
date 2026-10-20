"""DataSource schemas (spec #22, #37)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DataSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    source_type: str
    source_name: str
    source_url: str | None = None
    retrieved_at: datetime
    confidence: float | None = None
    provider: str | None = None
    # The ORM attribute is ``meta`` because ``metadata`` is reserved by
    # SQLAlchemy's declarative base.
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="meta",
        serialization_alias="metadata",
    )


class DataSourceList(BaseModel):
    items: list[DataSourceRead]
    total: int

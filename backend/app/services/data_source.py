"""User-scoped DataSource provenance (spec #22, #37, #57)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.data_source import DataSource


class DataSourceService:
    """Record and list the origin of externally sourced data.

    Every method requires an explicit ``user_id``; there is no unscoped query.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        user_id: uuid.UUID,
        source_type: str,
        source_name: str,
        source_url: str | None = None,
        provider: str | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DataSource:
        source = DataSource(
            user_id=user_id,
            source_type=source_type,
            source_name=source_name[:255],
            source_url=source_url,
            provider=provider,
            confidence=confidence,
            meta=metadata,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def get(self, *, user_id: uuid.UUID, source_id: uuid.UUID) -> DataSource | None:
        return self.db.scalar(
            select(DataSource).where(
                DataSource.id == source_id,
                DataSource.user_id == user_id,
            )
        )

    def list(
        self,
        *,
        user_id: uuid.UUID,
        source_type: str | None = None,
        limit: int = 50,
    ) -> tuple[list[DataSource], int]:
        filters = [DataSource.user_id == user_id]
        if source_type:
            filters.append(DataSource.source_type == source_type)
        total = self.db.scalar(select(func.count()).select_from(DataSource).where(*filters))
        rows = self.db.scalars(
            select(DataSource)
            .where(*filters)
            .order_by(DataSource.retrieved_at.desc(), DataSource.id)
            .limit(limit)
        )
        return list(rows), int(total or 0)

    def delete(self, *, user_id: uuid.UUID, source_id: uuid.UUID) -> bool:
        source = self.db.scalar(
            select(DataSource).where(
                DataSource.id == source_id,
                DataSource.user_id == user_id,
            )
        )
        if source is None:
            return False
        self.db.delete(source)
        self.db.commit()
        return True

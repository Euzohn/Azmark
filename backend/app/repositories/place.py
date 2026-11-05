from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.place import Place


class PlaceRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Place], int]:
        filters = [Place.user_id == user_id]
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    Place.name.ilike(like),
                    Place.localized_name.ilike(like),
                    Place.city.ilike(like),
                )
            )
        if type:
            filters.append(Place.type == type)

        order_by = (Place.name.asc(), Place.created_at.desc())
        total = self.db.scalar(select(func.count()).select_from(Place).where(*filters))
        stmt = (
            select(Place)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, place_id: uuid.UUID) -> Place | None:
        return self.db.scalar(select(Place).where(Place.id == place_id, Place.user_id == user_id))

    def create(self, place: Place) -> Place:
        self.db.add(place)
        self.db.commit()
        self.db.refresh(place)
        return place

    def save(self, place: Place) -> Place:
        self.db.add(place)
        self.db.commit()
        self.db.refresh(place)
        return place

    def delete(self, place: Place) -> None:
        self.db.delete(place)
        self.db.commit()

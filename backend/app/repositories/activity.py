from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models.activity import Activity


class ActivityRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        type: str | None = None,
        trip_id: uuid.UUID | None = None,
        place_id: uuid.UUID | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Activity], int]:
        filters = [Activity.user_id == user_id]
        if search:
            like = f"%{search}%"
            filters.append(or_(Activity.name.ilike(like), Activity.notes.ilike(like)))
        if type:
            filters.append(Activity.type == type)
        if trip_id is not None:
            filters.append(Activity.trip_id == trip_id)
        if place_id is not None:
            filters.append(Activity.place_id == place_id)

        if sort == "oldest":
            order_by = (Activity.start_at.asc().nullslast(), Activity.created_at.asc())
        elif sort == "created":
            order_by = (Activity.created_at.desc(), Activity.id)
        else:  # newest
            order_by = (Activity.start_at.desc().nullslast(), Activity.created_at.desc())

        total = self.db.scalar(select(func.count()).select_from(Activity).where(*filters))
        stmt = (
            select(Activity)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def list_for_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Activity]:
        stmt = (
            select(Activity)
            .where(Activity.user_id == user_id, Activity.trip_id == trip_id)
            .order_by(Activity.start_at.asc().nullslast(), Activity.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def get(self, *, user_id: uuid.UUID, activity_id: uuid.UUID) -> Activity | None:
        return self.db.scalar(
            select(Activity).where(Activity.id == activity_id, Activity.user_id == user_id)
        )

    def create(self, activity: Activity) -> Activity:
        self.db.add(activity)
        self.db.flush()
        self.db.refresh(activity)
        return activity

    def save(self, activity: Activity) -> Activity:
        self.db.add(activity)
        self.db.flush()
        self.db.refresh(activity)
        return activity

    def delete(self, activity: Activity) -> None:
        self.db.delete(activity)
        self.db.flush()

    def clear_place(self, *, user_id: uuid.UUID, place_id: uuid.UUID) -> None:
        """Detach activities from a place that is being deleted (spec #14)."""
        self.db.execute(
            update(Activity)
            .where(Activity.user_id == user_id, Activity.place_id == place_id)
            .values(place_id=None)
        )
        self.db.flush()

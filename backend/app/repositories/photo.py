from __future__ import annotations

import uuid

from sqlalchemy import func, nulls_last, select
from sqlalchemy.orm import Session

from app.models.photo import Photo


class PhotoRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        trip_id: uuid.UUID | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Photo], int]:
        filters = [Photo.user_id == user_id]
        if search:
            filters.append(Photo.filename.ilike(f"%{search}%"))
        if trip_id is not None:
            filters.append(Photo.trip_id == trip_id)

        # Photos without a capture time (screenshots, stripped EXIF) always sink
        # to the end of chronological sorts instead of pretending to be newest.
        if sort == "oldest":
            order_by = (
                nulls_last(Photo.captured_at.asc()),
                Photo.created_at.asc(),
                Photo.id,
            )
        elif sort == "uploaded":
            order_by = (Photo.created_at.desc(), Photo.id)
        else:  # newest
            order_by = (
                nulls_last(Photo.captured_at.desc()),
                Photo.created_at.desc(),
                Photo.id,
            )

        total = self.db.scalar(select(func.count()).select_from(Photo).where(*filters))
        stmt = (
            select(Photo)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, photo_id: uuid.UUID) -> Photo | None:
        return self.db.scalar(select(Photo).where(Photo.id == photo_id, Photo.user_id == user_id))

    def list_for_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Photo]:
        stmt = (
            select(Photo)
            .where(Photo.user_id == user_id, Photo.trip_id == trip_id)
            .order_by(nulls_last(Photo.captured_at.asc()), Photo.created_at.asc(), Photo.id)
        )
        return list(self.db.scalars(stmt))

    def list_for_user(self, *, user_id: uuid.UUID) -> list[Photo]:
        return list(self.db.scalars(select(Photo).where(Photo.user_id == user_id)))

    def create(self, photo: Photo, *, commit: bool = True) -> Photo:
        self.db.add(photo)
        self.db.commit() if commit else self.db.flush()
        self.db.refresh(photo)
        return photo

    def save(self, photo: Photo, *, commit: bool = True) -> Photo:
        self.db.add(photo)
        self.db.commit() if commit else self.db.flush()
        self.db.refresh(photo)
        return photo

    def delete(self, photo: Photo, *, commit: bool = True) -> None:
        self.db.delete(photo)
        self.db.commit() if commit else self.db.flush()

    def delete_many(self, photos: list[Photo], *, commit: bool = True) -> None:
        for photo in photos:
            self.db.delete(photo)
        self.db.commit() if commit else self.db.flush()

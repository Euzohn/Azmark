from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.note import Note


class NoteRepository:
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
    ) -> tuple[list[Note], int]:
        filters = [Note.user_id == user_id]
        if search:
            like = f"%{search}%"
            filters.append(or_(Note.title.ilike(like), Note.content.ilike(like)))
        if trip_id is not None:
            filters.append(Note.trip_id == trip_id)

        if sort == "oldest":
            order_by = (Note.created_at.asc(), Note.id)
        elif sort == "updated":
            order_by = (Note.updated_at.desc(), Note.id)
        elif sort == "title":
            order_by = (Note.title.asc(), Note.created_at.desc())
        else:  # newest
            order_by = (Note.created_at.desc(), Note.id)

        total = self.db.scalar(select(func.count()).select_from(Note).where(*filters))
        stmt = (
            select(Note)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, note_id: uuid.UUID) -> Note | None:
        return self.db.scalar(select(Note).where(Note.id == note_id, Note.user_id == user_id))

    def create(self, note: Note) -> Note:
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def save(self, note: Note) -> Note:
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete(self, note: Note) -> None:
        self.db.delete(note)
        self.db.commit()

import uuid

from sqlalchemy.orm import Session

from app.models.note import Note
from app.repositories.note import NoteRepository
from app.repositories.trip import TripRepository


class NoteNotFoundError(Exception):
    pass


class NoteTripAssignmentError(NoteNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class NoteService:
    """Note CRUD, scoped by user and optionally linked into a trip (spec #21)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.notes = NoteRepository(db)
        self.trips = TripRepository(db)

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise NoteTripAssignmentError

    def list_notes(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        trip_id: uuid.UUID | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Note], int]:
        return self.notes.list(
            user_id=user_id,
            search=search,
            trip_id=trip_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def get_note(self, *, user_id: uuid.UUID, note_id: uuid.UUID) -> Note:
        note = self.notes.get(user_id=user_id, note_id=note_id)
        if note is None:
            raise NoteNotFoundError
        return note

    def prepare_note(self, *, user_id: uuid.UUID, payload, validate_refs: bool = True) -> Note:
        """Validate an unsaved note (shared with the v2 importer)."""
        data = payload.model_dump()
        if validate_refs:
            self._check_trip(user_id=user_id, trip_id=data.get("trip_id"))
        return Note(user_id=user_id, **data)

    def create_note(self, *, user_id: uuid.UUID, payload) -> Note:
        return self.notes.create(self.prepare_note(user_id=user_id, payload=payload))

    def update_note(self, *, user_id: uuid.UUID, note_id: uuid.UUID, payload) -> Note:
        note = self.get_note(user_id=user_id, note_id=note_id)
        data = payload.model_dump(exclude_unset=True)
        if "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])

        # title is NOT NULL; an explicit null must not wipe it.
        if "title" in data and data["title"] is None:
            data.pop("title")

        for field, value in data.items():
            setattr(note, field, value)
        return self.notes.save(note)

    def delete_note(self, *, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
        note = self.get_note(user_id=user_id, note_id=note_id)
        self.notes.delete(note)

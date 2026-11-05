import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.repositories.activity import ActivityRepository
from app.repositories.place import PlaceRepository
from app.repositories.trip import TripRepository
from app.repositories.trip_item import TripItemRepository


class ActivityNotFoundError(Exception):
    pass


class ActivityTripAssignmentError(ActivityNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class ActivityPlaceAssignmentError(ActivityNotFoundError):
    """The referenced place does not exist or belongs to another user (spec #57)."""


class InvalidActivityWindowError(Exception):
    """The updated start/end window is inverted."""


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize for comparison (SQLite hands back naive datetimes)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ActivityService:
    """Activity CRUD, scoped by user and mirrored into the trip timeline (spec #18)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = ActivityRepository(db)
        self.trips = TripRepository(db)
        self.places = PlaceRepository(db)
        self.trip_items = TripItemRepository(db)

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise ActivityTripAssignmentError

    def _check_place(self, *, user_id: uuid.UUID, place_id: uuid.UUID | None) -> None:
        if place_id is not None and self.places.get(user_id=user_id, place_id=place_id) is None:
            raise ActivityPlaceAssignmentError

    def list_activities(
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
        return self.activities.list(
            user_id=user_id,
            search=search,
            type=type,
            trip_id=trip_id,
            place_id=place_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def get_activity(self, *, user_id: uuid.UUID, activity_id: uuid.UUID) -> Activity:
        activity = self.activities.get(user_id=user_id, activity_id=activity_id)
        if activity is None:
            raise ActivityNotFoundError
        return activity

    def create_activity(self, *, user_id: uuid.UUID, payload) -> Activity:
        data = payload.model_dump()
        self._check_trip(user_id=user_id, trip_id=data.get("trip_id"))
        self._check_place(user_id=user_id, place_id=data.get("place_id"))
        activity = Activity(user_id=user_id, **data)
        activity = self.activities.create(activity)
        self.trip_items.sync_activity(activity)
        return activity

    def update_activity(self, *, user_id: uuid.UUID, activity_id: uuid.UUID, payload) -> Activity:
        activity = self.get_activity(user_id=user_id, activity_id=activity_id)
        data = payload.model_dump(exclude_unset=True)
        if "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])
        if "place_id" in data:
            self._check_place(user_id=user_id, place_id=data["place_id"])

        # name is NOT NULL; an explicit null must not wipe it.
        if "name" in data and data["name"] is None:
            data.pop("name")

        # Validate the resulting window before touching the row, so a rejected
        # update leaves the session's object untouched.
        start = _as_utc(data.get("start_at", activity.start_at))
        end = _as_utc(data.get("end_at", activity.end_at))
        if start and end and end < start:
            raise InvalidActivityWindowError

        for field, value in data.items():
            setattr(activity, field, value)

        activity = self.activities.save(activity)
        self.trip_items.sync_activity(activity)
        return activity

    def delete_activity(self, *, user_id: uuid.UUID, activity_id: uuid.UUID) -> None:
        activity = self.get_activity(user_id=user_id, activity_id=activity_id)
        self.trip_items.delete_activity(user_id=user_id, activity_id=activity.id)
        self.activities.delete(activity)

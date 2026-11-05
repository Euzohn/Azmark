import uuid

from sqlalchemy.orm import Session

from app.models.place import Place
from app.repositories.activity import ActivityRepository
from app.repositories.place import PlaceRepository
from app.repositories.trip_item import TripItemRepository


class PlaceNotFoundError(Exception):
    pass


class PlaceService:
    """Place CRUD, scoped by user (spec #14, #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.places = PlaceRepository(db)
        self.trip_items = TripItemRepository(db)
        self.activities = ActivityRepository(db)

    def list_places(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Place], int]:
        return self.places.list(
            user_id=user_id, search=search, type=type, page=page, page_size=page_size
        )

    def get_place(self, *, user_id: uuid.UUID, place_id: uuid.UUID) -> Place:
        place = self.places.get(user_id=user_id, place_id=place_id)
        if place is None:
            raise PlaceNotFoundError
        return place

    def create_place(self, *, user_id: uuid.UUID, payload) -> Place:
        place = Place(user_id=user_id, **payload.model_dump())
        return self.places.create(place)

    def update_place(self, *, user_id: uuid.UUID, place_id: uuid.UUID, payload) -> Place:
        place = self.get_place(user_id=user_id, place_id=place_id)
        data = payload.model_dump(exclude_unset=True)
        # name is NOT NULL; an explicit null must not wipe it.
        if "name" in data and data["name"] is None:
            data.pop("name")
        for field, value in data.items():
            setattr(place, field, value)
        return self.places.save(place)

    def delete_place(self, *, user_id: uuid.UUID, place_id: uuid.UUID) -> None:
        place = self.get_place(user_id=user_id, place_id=place_id)
        self.trip_items.delete_place_items(user_id=user_id, place_id=place.id)
        self.activities.clear_place(user_id=user_id, place_id=place.id)
        self.places.delete(place)

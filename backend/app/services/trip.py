import uuid

from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.repositories.trip import TripRepository
from app.schemas.trip import TripCreate, TripUpdate


class TripNotFoundError(Exception):
    pass


class TripService:
    def __init__(self, db: Session) -> None:
        self.trips = TripRepository(db)

    def list_trips(
        self,
        *,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Trip], int]:
        return self.trips.list_trips(user_id=user_id, page=page, page_size=page_size)

    def get_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> Trip:
        trip = self.trips.get(user_id=user_id, trip_id=trip_id)
        if trip is None:
            raise TripNotFoundError
        return trip

    def list_records(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[TransportRecord]:
        return self.trips.list_records(user_id=user_id, trip_id=trip_id)

    def create_trip(self, *, user_id: uuid.UUID, payload: TripCreate) -> Trip:
        trip = Trip(user_id=user_id, **payload.model_dump())
        return self.trips.create(trip)

    def update_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID, payload: TripUpdate) -> Trip:
        trip = self.get_trip(user_id=user_id, trip_id=trip_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(trip, field, value)
        return self.trips.save(trip)

    def delete_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> None:
        trip = self.get_trip(user_id=user_id, trip_id=trip_id)
        self.trips.clear_records(user_id=user_id, trip_id=trip_id)
        self.trips.delete(trip)

import uuid

from sqlalchemy.orm import Session

from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.repositories.trip import TripRepository
from app.repositories.trip_item import TRANSPORT_ITEM, TripItemRepository
from app.schemas.transport import FlightRead
from app.schemas.trip import TripCreate, TripItemRead, TripItemUpdate, TripUpdate


class TripNotFoundError(Exception):
    pass


class TripItemNotFoundError(Exception):
    pass


class InvalidTripOrderError(Exception):
    """The supplied ordering does not match the trip's current items."""


class TripService:
    def __init__(self, db: Session) -> None:
        self.trips = TripRepository(db)
        self.items = TripItemRepository(db)

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

    def list_items(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[TripItemRead]:
        """Return trip items in display order with their transport record (#16)."""
        self.items.ensure_transport_items(user_id=user_id, trip_id=trip_id)
        records = {
            record.id: record for record in self.list_records(user_id=user_id, trip_id=trip_id)
        }
        return [
            TripItemRead(
                id=item.id,
                item_type=item.item_type,
                item_id=item.item_id,
                sort_order=item.sort_order,
                start_at=item.start_at,
                end_at=item.end_at,
                record=(
                    FlightRead.model_validate(records[item.item_id], from_attributes=True)
                    if item.item_type == TRANSPORT_ITEM and item.item_id in records
                    else None
                ),
            )
            for item in self.items.list_for_trip(user_id=user_id, trip_id=trip_id)
        ]

    def reorder_items(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, item_ids: list[uuid.UUID]
    ) -> None:
        self.get_trip(user_id=user_id, trip_id=trip_id)
        self.items.ensure_transport_items(user_id=user_id, trip_id=trip_id)
        current_ids = [
            item.id for item in self.items.list_for_trip(user_id=user_id, trip_id=trip_id)
        ]
        if len(item_ids) != len(set(item_ids)) or set(item_ids) != set(current_ids):
            raise InvalidTripOrderError
        self.items.set_order(user_id=user_id, trip_id=trip_id, item_ids=item_ids)

    def update_item(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: TripItemUpdate,
    ) -> None:
        self.get_trip(user_id=user_id, trip_id=trip_id)
        item = self.items.get(user_id=user_id, trip_id=trip_id, item_id=item_id)
        if item is None:
            raise TripItemNotFoundError
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        self.items.save(item)

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

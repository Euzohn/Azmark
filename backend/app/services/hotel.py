import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.models.hotel import Hotel
from app.repositories.hotel import HotelRepository
from app.repositories.trip import TripRepository
from app.repositories.trip_item import TripItemRepository
from app.services.dedup import hotel_signature
from app.services.expense_source import SOURCE_HOTEL, clear_source, sync_source_trip


class HotelNotFoundError(Exception):
    pass


class HotelTripAssignmentError(HotelNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class DuplicateHotelError(Exception):
    """A hotel with the same deduplication key already exists (spec #41)."""

    def __init__(self, existing_hotel: Hotel) -> None:
        self.existing_hotel = existing_hotel
        super().__init__("Duplicate hotel")


class HotelService:
    """Hotel CRUD, scoped by user and linked into trips (spec #17, #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.hotels = HotelRepository(db)
        self.trips = TripRepository(db)
        self.trip_items = TripItemRepository(db)

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise HotelTripAssignmentError

    def _check_duplicate(
        self, *, user_id: uuid.UUID, hotel: str, check_in: date, check_out: date | None
    ) -> Hotel | None:
        sig = hotel_signature(check_in=check_in, hotel_name=hotel, check_out=check_out)
        return self.hotels.find_by_signature(user_id=user_id, signature=sig)

    @staticmethod
    def _infer_status(*, check_in: date, check_out: date | None, current: str | None) -> str:
        """Derive scheduled/completed from the stay dates unless explicitly set.

        An explicit status always wins so a cancelled stay stays cancelled even
        once its dates pass.
        """
        if current:
            return current
        end = check_out or check_in
        return "completed" if end < date.today() else "scheduled"

    def list_hotels(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        status: str | None = None,
        trip_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Hotel], int]:
        return self.hotels.list(
            user_id=user_id,
            search=search,
            status=status,
            trip_id=trip_id,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def get_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> Hotel:
        hotel = self.hotels.get(user_id=user_id, hotel_id=hotel_id)
        if hotel is None:
            raise HotelNotFoundError
        return hotel

    def create_hotel(self, *, user_id: uuid.UUID, payload, force: bool = False) -> Hotel:
        data = payload.model_dump()
        self._check_trip(user_id=user_id, trip_id=data.get("trip_id"))

        if not force:
            existing = self._check_duplicate(
                user_id=user_id,
                hotel=data["hotel"],
                check_in=data["check_in"],
                check_out=data.get("check_out"),
            )
            if existing is not None:
                raise DuplicateHotelError(existing)

        # Confirmation numbers are sensitive (spec #45/#96): store ciphertext only.
        booking_reference = data.pop("booking_reference", None)
        data["status"] = self._infer_status(
            check_in=data["check_in"],
            check_out=data.get("check_out"),
            current=data.get("status") if data.get("status") != "scheduled" else None,
        )
        hotel = Hotel(user_id=user_id, **data)
        if booking_reference:
            hotel.booking_reference_enc = encrypt_value(booking_reference)
        hotel = self.hotels.create(hotel)
        self.trip_items.sync_hotel(hotel)
        self.db.commit()
        return hotel

    def update_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID, payload) -> Hotel:
        hotel = self.get_hotel(user_id=user_id, hotel_id=hotel_id)
        data = payload.model_dump(exclude_unset=True)
        if "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])

        if "booking_reference" in data:
            value = data.pop("booking_reference")
            hotel.booking_reference_enc = encrypt_value(value) if value else None

        # Only re-infer when a date actually moved and the caller did not pin a
        # status in this request.
        if "status" not in data and ("check_in" in data or "check_out" in data):
            data["status"] = self._infer_status(
                check_in=data.get("check_in", hotel.check_in),
                check_out=data.get("check_out", hotel.check_out),
                current=None,
            )

        for field, value in data.items():
            setattr(hotel, field, value)
        sync_source_trip(
            self.db,
            user_id=user_id,
            source_type=SOURCE_HOTEL,
            source_id=hotel.id,
            trip_id=hotel.trip_id,
        )
        hotel = self.hotels.save(hotel)
        self.trip_items.sync_hotel(hotel)
        self.db.commit()
        return hotel

    def delete_hotel(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> None:
        hotel = self.get_hotel(user_id=user_id, hotel_id=hotel_id)
        clear_source(self.db, user_id=user_id, source_type=SOURCE_HOTEL, source_id=hotel.id)
        self.trip_items.delete_hotel(user_id=user_id, hotel_id=hotel.id)
        self.hotels.delete(hotel)
        self.db.commit()

    def set_coordinates(
        self, *, user_id: uuid.UUID, hotel_id: uuid.UUID, lat: float, lon: float
    ) -> Hotel:
        """Attach map coordinates from the explicit geocode action (spec #10)."""
        hotel = self.get_hotel(user_id=user_id, hotel_id=hotel_id)
        hotel.lat = lat
        hotel.lon = lon
        hotel = self.hotels.save(hotel)
        self.db.commit()
        return hotel

    # -- pending-action surface ------------------------------------------------
    # The approval inbox (spec #69) executes proposals through the same method
    # names the transport services expose, so an agent can propose a hotel stay
    # the same way it proposes a flight. These delegate to the hotel-specific
    # methods above.
    def create_record(self, *, user_id: uuid.UUID, payload, force: bool = False) -> Hotel:
        return self.create_hotel(user_id=user_id, payload=payload, force=force)

    def update_record(self, *, user_id: uuid.UUID, record_id: uuid.UUID, payload) -> Hotel:
        return self.update_hotel(user_id=user_id, hotel_id=record_id, payload=payload)

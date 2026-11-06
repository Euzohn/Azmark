from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.hotel import Hotel


class HotelRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
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
        filters = [Hotel.user_id == user_id]
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    Hotel.hotel.ilike(like),
                    Hotel.address.ilike(like),
                    Hotel.room_type.ilike(like),
                )
            )
        if status:
            filters.append(Hotel.status == status)
        if trip_id is not None:
            filters.append(Hotel.trip_id == trip_id)
        if date_from is not None:
            filters.append(Hotel.check_in >= date_from)
        if date_to is not None:
            filters.append(Hotel.check_in <= date_to)

        # Sort options mirror the records list. Hotels key on check_in instead of
        # a departure time, so "departure"/"arrival" collapse to check-in/out.
        if sort == "oldest":
            order_by = (Hotel.check_in.asc().nullslast(), Hotel.created_at.asc())
        elif sort == "check_out":
            order_by = (Hotel.check_out.asc().nullslast(), Hotel.created_at.asc())
        elif sort == "created":
            order_by = (Hotel.created_at.desc(), Hotel.id)
        else:  # newest — most recent check-in first
            order_by = (Hotel.check_in.desc().nullslast(), Hotel.created_at.desc())

        total = self.db.scalar(select(func.count()).select_from(Hotel).where(*filters))
        stmt = (
            select(Hotel)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, hotel_id: uuid.UUID) -> Hotel | None:
        return self.db.scalar(select(Hotel).where(Hotel.id == hotel_id, Hotel.user_id == user_id))

    def list_for_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Hotel]:
        stmt = (
            select(Hotel)
            .where(Hotel.user_id == user_id, Hotel.trip_id == trip_id)
            .order_by(Hotel.check_in.asc().nullslast(), Hotel.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def search(
        self,
        *,
        user_id: uuid.UUID,
        query: str,
        limit: int = 20,
    ) -> list[Hotel]:
        """Keyword search across a user's hotels (spec #31, #57)."""
        like = f"%{query}%"
        stmt = (
            select(Hotel)
            .where(
                Hotel.user_id == user_id,
                or_(
                    Hotel.hotel.ilike(like),
                    Hotel.address.ilike(like),
                    Hotel.room_type.ilike(like),
                ),
            )
            .order_by(Hotel.check_in.desc().nullslast(), Hotel.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def create(self, hotel: Hotel) -> Hotel:
        self.db.add(hotel)
        self.db.flush()
        self.db.refresh(hotel)
        return hotel

    def save(self, hotel: Hotel) -> Hotel:
        self.db.add(hotel)
        self.db.flush()
        self.db.refresh(hotel)
        return hotel

    def delete(self, hotel: Hotel) -> None:
        self.db.delete(hotel)
        self.db.flush()

    def find_by_signature(
        self,
        *,
        user_id: uuid.UUID,
        signature: str,
    ) -> Hotel | None:
        """Find a hotel by its deduplication signature (spec #41).

        Signature format: hotel|check_in|hotel_name|check_out
        """
        parts = signature.split("|", 3)
        if len(parts) != 4:
            return None
        _, check_in_str, name, check_out_str = parts

        filters = [Hotel.user_id == user_id]
        try:
            filters.append(Hotel.check_in == date.fromisoformat(check_in_str))
        except ValueError:
            return None

        def _match(column, value: str):
            return column.ilike(value) if value else column.is_(None)

        filters.append(_match(func.lower(Hotel.hotel), name))
        if check_out_str:
            try:
                filters.append(Hotel.check_out == date.fromisoformat(check_out_str))
            except ValueError:
                return None
        else:
            filters.append(Hotel.check_out.is_(None))

        stmt = select(Hotel).where(*filters)
        return self.db.scalar(stmt)

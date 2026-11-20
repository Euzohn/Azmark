"""Deterministic photo-to-trip suggestions (P2 AI Photo Organization, spec #20).

Matching is plain EXIF time + GPS geometry, not an LLM guess: the AI layer
reads these facts and proposes assignments that the user explicitly confirms.
Face clustering and reverse-geocoded filenames are deliberately out of scope.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.activity import Activity
from app.models.hotel import Hotel
from app.models.photo import Photo
from app.models.trip import Trip
from app.repositories.photo import PhotoRepository
from app.repositories.trip import TripRepository
from app.services.photo import PhotoNotFoundError, PhotoTripAssignmentError
from app.services.write_lock import lock_user_writes
from app.utils.geo import haversine_km

#: A photo within this radius of a trip's hotel/place counts as a geo match;
#: it covers a city plus its airport runs without reaching the next city.
GEO_MATCH_RADIUS_KM = 50.0

#: Keep the review panel and the organize endpoint's batch limit in sync:
#: suggesting more than can be confirmed at once would 422 on apply.
MAX_SUGGESTIONS = 200

_CONFIDENCE_RANK = {"strong": 0, "medium": 1, "weak": 2}


@dataclass(frozen=True)
class TripCandidate:
    trip: Trip
    reasons: list[str]
    distance_km: float | None

    @property
    def confidence(self) -> str:
        if "time" in self.reasons and "geo" in self.reasons:
            return "strong"
        return "medium" if "time" in self.reasons else "weak"


class PhotoOrganizationService:
    """Suggest trip assignments for unfiled photos; apply confirmed batches."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.photos = PhotoRepository(db)
        self.trips = TripRepository(db)

    def _trip_anchors(self, user_id: uuid.UUID) -> dict[uuid.UUID, list[tuple[float, float]]]:
        """Geolocated hotels and activity places per trip, in two queries."""
        anchors: dict[uuid.UUID, list[tuple[float, float]]] = {}
        hotels = self.db.scalars(
            select(Hotel).where(
                Hotel.user_id == user_id,
                Hotel.trip_id.is_not(None),
                Hotel.lat.is_not(None),
                Hotel.lon.is_not(None),
            )
        ).all()
        for hotel in hotels:
            anchors.setdefault(hotel.trip_id, []).append((hotel.lat, hotel.lon))
        activities = self.db.scalars(
            select(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.trip_id.is_not(None),
                Activity.place_id.is_not(None),
            )
            .options(joinedload(Activity.place))
        ).all()
        for activity in activities:
            place = activity.place
            if place is not None and place.lat is not None and place.lon is not None:
                anchors.setdefault(activity.trip_id, []).append((place.lat, place.lon))
        return anchors

    def suggest(self, *, user_id: uuid.UUID) -> tuple[list[tuple[Photo, list[TripCandidate]]], int]:
        """Return (photo, ranked candidates) pairs plus the unfiled total.

        Photos without both EXIF time and GPS cannot be matched and are
        skipped; ambiguous photos keep every candidate — nothing is auto-filed.
        """
        unassigned = self.db.scalars(
            select(Photo).where(Photo.user_id == user_id, Photo.trip_id.is_(None))
        ).all()
        trips = self.db.scalars(select(Trip).where(Trip.user_id == user_id)).all()
        anchors = self._trip_anchors(user_id)

        items: list[tuple[Photo, list[TripCandidate]]] = []
        for photo in unassigned:
            if photo.captured_at is None and photo.latitude is None:
                continue
            candidates: list[TripCandidate] = []
            for trip in trips:
                reasons: list[str] = []
                distance: float | None = None
                # Dates compare in UTC: a photo near local midnight can land on
                # the adjacent day, which is acceptable for a suggestion.
                if (
                    photo.captured_at is not None
                    and trip.start_date is not None
                    and trip.end_date is not None
                    and trip.start_date <= photo.captured_at.date() <= trip.end_date
                ):
                    reasons.append("time")
                if photo.latitude is not None and photo.longitude is not None:
                    points = anchors.get(trip.id, [])
                    if points:
                        nearest = min(
                            haversine_km(photo.latitude, photo.longitude, lat, lon)
                            for lat, lon in points
                        )
                        if nearest <= GEO_MATCH_RADIUS_KM:
                            reasons.append("geo")
                            distance = round(nearest, 1)
                if reasons:
                    candidates.append(
                        TripCandidate(trip=trip, reasons=reasons, distance_km=distance)
                    )
            if candidates:
                candidates.sort(
                    key=lambda candidate: (
                        _CONFIDENCE_RANK[candidate.confidence],
                        candidate.trip.name,
                    )
                )
                items.append((photo, candidates))
        items.sort(key=lambda pair: pair[0].captured_at or pair[0].created_at, reverse=True)
        return items[:MAX_SUGGESTIONS], len(unassigned)

    def organize(
        self, *, user_id: uuid.UUID, assignments: list[tuple[uuid.UUID, uuid.UUID]]
    ) -> int:
        """Apply a user-confirmed batch; all-or-nothing on ownership checks."""
        lock_user_writes(self.db, user_id)
        resolved: list[tuple[Photo, uuid.UUID]] = []
        for photo_id, trip_id in assignments:
            photo = self.photos.get(user_id=user_id, photo_id=photo_id)
            if photo is None:
                raise PhotoNotFoundError
            if self.trips.get(user_id=user_id, trip_id=trip_id) is None:
                raise PhotoTripAssignmentError
            resolved.append((photo, trip_id))
        for photo, trip_id in resolved:
            photo.trip_id = trip_id
        self.db.commit()
        return len(resolved)

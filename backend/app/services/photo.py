"""Photo records: EXIF-aware upload, listing, and safe inline serving (#20, #44).

The binary goes through the StorageProvider; PostgreSQL only keeps metadata.
``storage_key`` never leaves the server — images are served from an
authenticated endpoint with ``nosniff`` and an image-only MIME whitelist, so
there is no script-bearing format (SVG/HTML) to worry about.
"""

from __future__ import annotations

import io
import logging
import re
import struct
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.photo import Photo
from app.repositories.photo import PhotoRepository
from app.repositories.trip import TripRepository
from app.services.storage import (
    StorageError,
    StorageObjectNotFound,
    StorageProvider,
)
from app.services.storage_quota import enforce_storage_quota
from app.services.write_lock import lock_user_writes

logger = logging.getLogger(__name__)

# Only raster formats the browser renders safely. SVG and HTML are excluded
# because they can execute scripts when served inline (spec #44/#70).
ALLOWED_PHOTO_FORMATS: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}

THUMBNAIL_SIZE = (480, 480)
THUMBNAIL_MIME = "image/jpeg"
# 60MP covers 48MP phone cameras and most panoramas while keeping the RGB
# decode buffer near 180MB; bigger files are almost always desktop exports.
MAX_PHOTO_PIXELS = 60_000_000

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_TAG_DATETIME = 306
_TAG_DATETIME_ORIGINAL = 36867
_TAG_DATETIME_DIGITIZED = 36868
_TAG_OFFSET_TIME_ORIGINAL = 36881
_GPS_LATITUDE_REF = 1
_GPS_LATITUDE = 2
_GPS_LONGITUDE_REF = 3
_GPS_LONGITUDE = 4
_UTC_OFFSET_RE = re.compile(r"^(?:UTC)?([+-])(\d{2}):?(\d{2})$")


class PhotoError(Exception):
    pass


class PhotoNotFoundError(PhotoError):
    pass


class PhotoTripAssignmentError(PhotoNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class UnsupportedPhotoTypeError(PhotoError):
    pass


class InvalidPhotoError(PhotoError):
    pass


class PhotoTooLargeError(PhotoError):
    pass


class EmptyPhotoError(PhotoError):
    pass


class PhotoStorageUnavailableError(PhotoError):
    pass


@dataclass(frozen=True)
class PhotoMetadata:
    mime_type: str
    width: int
    height: int
    captured_at: datetime | None
    latitude: float | None
    longitude: float | None


def _clean_filename(filename: str | None) -> str:
    name = (filename or "photo").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if char.isprintable()).strip()
    return name[:255] or "photo"


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("ascii", "ignore").strip("\x00").strip()
    return str(value).strip()


def _parse_utc_offset(value: object) -> timezone | None:
    """Parse EXIF ``OffsetTimeOriginal`` ("+08:00", "Z", "-0500")."""
    text = _as_text(value)
    if not text:
        return None
    if text.upper() == "Z":
        return UTC
    match = _UTC_OFFSET_RE.match(text)
    if match is None:
        return None
    sign, hours, minutes = match.groups()
    if int(hours) > 14 or int(minutes) > 59:
        return None
    delta = timedelta(hours=int(hours), minutes=int(minutes))
    return timezone(-delta if sign == "-" else delta)


def _exif_datetime(sub_ifd: dict, ifd0: dict, utc_offset_minutes: int | None) -> datetime | None:
    raw = (
        sub_ifd.get(_TAG_DATETIME_ORIGINAL)
        or sub_ifd.get(_TAG_DATETIME_DIGITIZED)
        or ifd0.get(_TAG_DATETIME)
    )
    text = _as_text(raw)
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    # Cameras usually record wall-clock time without a zone. Prefer the EXIF
    # offset tag, then the browser's offset at upload time (EXIF time is local
    # to where the photo was taken), and only then assume UTC. Normalise to UTC
    # before it reaches the database: SQLite drops offsets, Postgres does not.
    offset = _parse_utc_offset(sub_ifd.get(_TAG_OFFSET_TIME_ORIGINAL))
    if offset is not None:
        return parsed.replace(tzinfo=offset).astimezone(UTC)
    if utc_offset_minutes is not None:
        return parsed.replace(tzinfo=timezone(timedelta(minutes=utc_offset_minutes))).astimezone(
            UTC
        )
    return parsed.replace(tzinfo=UTC)


def _dms_to_degrees(value: object) -> float | None:
    try:
        parts = [float(part) for part in value]  # type: ignore[union-attr]
    except (TypeError, ValueError):
        return None
    if len(parts) != 3:
        return None
    degrees, minutes, seconds = parts
    if not 0 <= minutes < 60 or not 0 <= seconds < 60:
        return None
    return degrees + minutes / 60 + seconds / 3600


def _exif_gps(ifd0: dict) -> tuple[float | None, float | None]:
    try:
        gps = ifd0.get_ifd(_GPS_IFD)
    except Exception:  # malformed GPS IFD must never block an upload
        return None, None
    if not gps:
        return None, None
    latitude = _dms_to_degrees(gps.get(_GPS_LATITUDE))
    longitude = _dms_to_degrees(gps.get(_GPS_LONGITUDE))
    if latitude is None or longitude is None:
        return None, None
    if (_as_text(gps.get(_GPS_LATITUDE_REF)) or "").upper() == "S":
        latitude = -latitude
    if (_as_text(gps.get(_GPS_LONGITUDE_REF)) or "").upper() == "W":
        longitude = -longitude
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None, None
    return round(latitude, 7), round(longitude, 7)


def _exif_metadata(
    img: Image.Image, utc_offset_minutes: int | None
) -> tuple[datetime | None, float | None, float | None]:
    try:
        ifd0 = img.getexif()
    except Exception:  # unreadable EXIF is not a reason to reject the photo
        return None, None, None
    try:
        sub_ifd = ifd0.get_ifd(_EXIF_IFD)
    except Exception:
        sub_ifd = {}
    captured_at = _exif_datetime(sub_ifd, ifd0, utc_offset_minutes)
    latitude, longitude = _exif_gps(ifd0)
    return captured_at, latitude, longitude


def _thumbnail_bytes(img: Image.Image) -> bytes:
    """Downscale to a browser-friendly JPEG, honouring EXIF orientation."""
    frame = ImageOps.exif_transpose(img)
    frame.thumbnail(THUMBNAIL_SIZE)
    if frame.mode in ("RGBA", "LA", "P"):
        rgba = frame.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
        flattened.paste(rgba, mask=rgba.getchannel("A"))
        frame = flattened
    elif frame.mode != "RGB":
        frame = frame.convert("RGB")
    out = io.BytesIO()
    frame.save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue()


def process_photo(
    data: bytes, *, utc_offset_minutes: int | None = None
) -> tuple[PhotoMetadata, bytes]:
    """Validate the bytes as a supported image and return metadata + thumbnail.

    Pillow is also the MIME check: the declared content type is irrelevant,
    the actual decoded format decides what we store and serve.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            # DJI drones and dual-lens cameras wrap extra frames in an MPO
            # container named .JPG. The first frame is a plain JPEG that
            # browsers render, so accept it as JPEG instead of rejecting it.
            if fmt == "MPO":
                fmt = "JPEG"
            mime = ALLOWED_PHOTO_FORMATS.get(fmt)
            if mime is None:
                raise UnsupportedPhotoTypeError(fmt or "unknown")
            if img.width * img.height > MAX_PHOTO_PIXELS:
                raise PhotoTooLargeError
            img.load()  # force a full decode so truncated files are rejected
            captured_at, latitude, longitude = _exif_metadata(img, utc_offset_minutes)
            metadata = PhotoMetadata(
                mime_type=mime,
                width=img.width,
                height=img.height,
                captured_at=captured_at,
                latitude=latitude,
                longitude=longitude,
            )
            return metadata, _thumbnail_bytes(img)
    except (UnsupportedPhotoTypeError, PhotoTooLargeError):
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
        struct.error,
    ) as exc:
        # Pillow raises decoder-specific errors for corrupt uploads; they all
        # mean "not a usable image" to the caller.
        raise InvalidPhotoError from exc


class PhotoService:
    """Photo CRUD plus object-storage lifecycle, scoped by user (spec #57)."""

    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self.db = db
        self.photos = PhotoRepository(db)
        self.trips = TripRepository(db)
        self.storage = storage

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise PhotoTripAssignmentError

    def list_photos(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        trip_id: uuid.UUID | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Photo], int]:
        return self.photos.list(
            user_id=user_id,
            search=search,
            trip_id=trip_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def get_photo(self, *, user_id: uuid.UUID, photo_id: uuid.UUID) -> Photo:
        photo = self.photos.get(user_id=user_id, photo_id=photo_id)
        if photo is None:
            raise PhotoNotFoundError
        return photo

    def upload(
        self,
        *,
        user_id: uuid.UUID,
        filename: str | None,
        stream: BinaryIO,
        trip_id: uuid.UUID | None = None,
        utc_offset_minutes: int | None = None,
    ) -> Photo:
        lock_user_writes(self.db, user_id)
        self._check_trip(user_id=user_id, trip_id=trip_id)

        max_bytes = settings.max_attachment_bytes
        data = stream.read(max_bytes + 1)
        if not data:
            raise EmptyPhotoError
        if len(data) > max_bytes:
            raise PhotoTooLargeError

        # Inside the user write lock: concurrent uploads cannot overshoot.
        enforce_storage_quota(self.db, user_id=user_id, incoming_bytes=len(data))

        metadata, thumbnail = process_photo(data, utc_offset_minutes=utc_offset_minutes)

        photo_id = uuid.uuid4()
        storage_key = f"users/{user_id}/photos/{photo_id}"
        thumbnail_key = f"{storage_key}/thumb"
        try:
            self.storage.put(key=storage_key, data=data, content_type=metadata.mime_type)
            self.storage.put(key=thumbnail_key, data=thumbnail, content_type=THUMBNAIL_MIME)
        except StorageError as exc:
            self._delete_object_best_effort(storage_key, photo_id)
            self._delete_object_best_effort(thumbnail_key, photo_id)
            raise PhotoStorageUnavailableError from exc

        photo = Photo(
            id=photo_id,
            user_id=user_id,
            storage_key=storage_key,
            filename=_clean_filename(filename),
            mime_type=metadata.mime_type,
            size=len(data),
            captured_at=metadata.captured_at,
            latitude=metadata.latitude,
            longitude=metadata.longitude,
            trip_id=trip_id,
        )
        try:
            return self.photos.create(photo)
        except Exception:
            # Never leave objects behind if the metadata insert fails.
            self._delete_object_best_effort(storage_key, photo_id)
            self._delete_object_best_effort(thumbnail_key, photo_id)
            raise

    def update_photo(
        self, *, user_id: uuid.UUID, photo_id: uuid.UUID, payload, commit: bool = True
    ) -> Photo:
        lock_user_writes(self.db, user_id)
        photo = self.get_photo(user_id=user_id, photo_id=photo_id)
        data = payload.model_dump(exclude_unset=True)
        if "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])

        # filename is NOT NULL; an explicit null must not wipe it.
        if "filename" in data:
            if data["filename"] is None:
                data.pop("filename")
            else:
                data["filename"] = _clean_filename(data["filename"])

        # Store one canonical instant regardless of the offset the client sent;
        # a naive value is UTC by contract (spec: all API timestamps are UTC).
        if data.get("captured_at") is not None:
            captured_at = data["captured_at"]
            if captured_at.tzinfo is None:
                data["captured_at"] = captured_at.replace(tzinfo=UTC)
            else:
                data["captured_at"] = captured_at.astimezone(UTC)

        for field, value in data.items():
            setattr(photo, field, value)
        return self.photos.save(photo, commit=commit)

    def delete_photo(
        self, *, user_id: uuid.UUID, photo_id: uuid.UUID, commit: bool = True
    ) -> list[tuple[str, uuid.UUID]]:
        """Remove metadata; return the object keys to delete after commit."""
        lock_user_writes(self.db, user_id)
        photo = self.get_photo(user_id=user_id, photo_id=photo_id)
        objects = [
            (photo.storage_key, photo.id),
            (f"{photo.storage_key}/thumb", photo.id),
        ]
        self.photos.delete(photo, commit=commit)
        return objects

    def image(
        self, *, user_id: uuid.UUID, photo_id: uuid.UUID, variant: str = "full"
    ) -> tuple[Photo, bytes, str]:
        photo = self.get_photo(user_id=user_id, photo_id=photo_id)
        if variant == "thumb":
            key, mime = f"{photo.storage_key}/thumb", THUMBNAIL_MIME
        else:
            key, mime = photo.storage_key, photo.mime_type
        try:
            data = self.storage.get(key=key)
        except StorageObjectNotFound as exc:
            raise PhotoNotFoundError from exc
        except StorageError as exc:
            raise PhotoStorageUnavailableError from exc
        return photo, data, mime

    def cleanup_staged_objects(self, objects: list[tuple[str, uuid.UUID]]) -> None:
        for storage_key, photo_id in objects:
            self._delete_object_best_effort(storage_key, photo_id)

    def delete_for_user(self, *, user_id: uuid.UUID) -> None:
        """Cascade cleanup before deleting an account (spec #48)."""
        photos = self.photos.list_for_user(user_id=user_id)
        for photo in photos:
            self._delete_object_best_effort(photo.storage_key, photo.id)
            self._delete_object_best_effort(f"{photo.storage_key}/thumb", photo.id)
        if photos:
            self.photos.delete_many(photos)

    def _delete_object_best_effort(self, storage_key: str, photo_id: uuid.UUID) -> None:
        try:
            self.storage.delete(key=storage_key)
        except StorageError:
            # Do not block deletion on an unavailable backend; log only the
            # opaque id, never the user's filename or storage key.
            logger.warning("Could not delete photo object %s", photo_id)

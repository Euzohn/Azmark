"""Unified records list across transport types (spec #23/#57)."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_record_service
from app.models.user import User
from app.schemas.record import RecordList
from app.schemas.status import RecordStatus
from app.schemas.transport import FlightRead
from app.services.record import RecordService

router = APIRouter(prefix="/records", tags=["records"])

RecordType = Literal["flight", "train", "other"]
RecordSort = Literal["newest", "oldest", "departure", "arrival", "created"]


@router.get("", response_model=RecordList)
def list_records(
    search: str | None = None,
    type_filter: RecordType | None = Query(default=None, alias="type"),
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
    cabin_class: str | None = None,
    carrier: str | None = None,
    trip_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: RecordSort = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
) -> RecordList:
    items, total = service.list_records(
        user_id=current_user.id,
        record_type=type_filter,
        search=search,
        status=status_filter,
        cabin_class=cabin_class,
        carrier=carrier,
        trip_id=trip_id,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return RecordList(items=items, total=total, page=page, page_size=page_size)


@router.get("/{record_id}", response_model=FlightRead)
def get_record(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
) -> FlightRead:
    """Fetch one transport record regardless of its type.

    The expense source card uses this to resolve a linked record's detail
    route (/flights, /trains or /transports) from its id alone.
    """
    record = service.records.get(user_id=current_user.id, record_id=record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return record

"""Unified records list across transport types (spec #23/#57)."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_record_service
from app.models.user import User
from app.schemas.record import RecordList
from app.services.record import RecordService

router = APIRouter(prefix="/records", tags=["records"])

RecordType = Literal["flight", "train", "other"]
RecordSort = Literal["newest", "oldest", "departure", "arrival", "created"]


@router.get("", response_model=RecordList)
def list_records(
    search: str | None = None,
    type_filter: RecordType | None = Query(default=None, alias="type"),
    status_filter: str | None = Query(default=None, alias="status"),
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

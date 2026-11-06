import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.activity import ActivityRead
from app.schemas.attachment import AttachmentRead
from app.schemas.expense import ExpenseRead, ExpenseSummary
from app.schemas.hotel import HotelRead
from app.schemas.note import NoteRead
from app.schemas.status import TripStatus
from app.schemas.transport import FlightRead

TimelineOrderMode = Literal["chronological", "manual"]


class _TripDates(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> "_TripDates":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class TripBase(_TripDates):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    status: str = Field(default="planned", max_length=20)
    timeline_order_mode: TimelineOrderMode = "chronological"


class TripCreate(TripBase):
    status: TripStatus = "planned"


class TripUpdate(_TripDates):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    status: TripStatus | None = None
    timeline_order_mode: TimelineOrderMode | None = None


class TripRead(TripBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TripItemRead(BaseModel):
    """Ordered trip member (spec #16).

    Times are computed from the source entity; ``trip_items`` no longer owns
    them. ``record`` is populated for transport items, ``hotel`` for
    accommodation and ``activity`` for activities; exactly one payload is set
    per item.

    ``time_kind`` distinguishes an instant (transport/activity) from a date
    range (hotel). ``is_unscheduled`` marks rows without a start time.
    """

    id: uuid.UUID | None = None
    item_type: str
    item_id: uuid.UUID
    sort_order: int
    time_kind: Literal["instant", "date"] = "instant"
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str | None = None
    is_unscheduled: bool = False
    record: FlightRead | None = None
    hotel: HotelRead | None = None
    activity: ActivityRead | None = None


class TripItemCreate(BaseModel):
    """Add a place to a trip as a visit Activity (legacy facade, spec #9.1)."""

    model_config = ConfigDict(extra="forbid")

    item_type: Literal["place"]
    item_id: uuid.UUID
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _check_window(self) -> "TripItemCreate":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("end_at must not be before start_at")
        return self


class TripItemUpdate(BaseModel):
    """Only the display order. Event times must be changed at the source.

    ``extra="forbid"`` turns a stale client sending ``start_at`` into a 422
    instead of silently ignoring it.
    """

    model_config = ConfigDict(extra="forbid")

    sort_order: int | None = Field(default=None, ge=0)


class TripItemOrder(BaseModel):
    item_ids: list[uuid.UUID]


class TripDetail(TripRead):
    """Trip plus ordered items, grouped records, expenses, notes and attachments."""

    records: list[FlightRead] = []
    items: list[TripItemRead] = []
    expenses: list[ExpenseRead] = []
    expense_summary: ExpenseSummary | None = None
    notes: list[NoteRead] = []
    attachments: list[AttachmentRead] = []


class TripList(BaseModel):
    items: list[TripRead]
    total: int
    page: int
    page_size: int

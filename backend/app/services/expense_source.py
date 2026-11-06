"""Keep linked expenses in step with their source record (docs §6.3–6.4).

All helpers only ``flush``/``execute``; the caller owns the transaction so the
source change, its timeline projection and the expense assignment commit (or
roll back) together.
"""

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.expense import Expense

SOURCE_TRANSPORT = "transport"
SOURCE_HOTEL = "hotel"
SOURCE_ACTIVITY = "activity"


def sync_source_trip(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    trip_id: uuid.UUID | None,
) -> None:
    """Move every expense linked to the source to the source's current trip."""
    db.execute(
        update(Expense)
        .where(
            Expense.user_id == user_id,
            Expense.source_type == source_type,
            Expense.source_id == source_id,
        )
        .values(trip_id=trip_id)
    )


def clear_source(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
) -> None:
    """Detach expenses before deleting their source, keeping the trip snapshot."""
    db.execute(
        update(Expense)
        .where(
            Expense.user_id == user_id,
            Expense.source_type == source_type,
            Expense.source_id == source_id,
        )
        .values(source_type=None, source_id=None)
    )

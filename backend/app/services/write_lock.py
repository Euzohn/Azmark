"""Serialize related timeline and expense mutations for one user.

The user row is the common lock acquired before reading any mutable source or
trip state. PostgreSQL holds it until the outer transaction ends; SQLite tests
exercise the same business rules without claiming to test row locking.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def lock_user_writes(db: Session, user_id: uuid.UUID) -> None:
    db.scalar(select(User.id).where(User.id == user_id).with_for_update())

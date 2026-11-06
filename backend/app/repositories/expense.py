from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.expense import Expense


class ExpenseRepository:
    """All queries are scoped by user_id — callers must never bypass it (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        category: str | None = None,
        trip_id: uuid.UUID | None = None,
        source_type: str | None = None,
        source_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Expense], int]:
        filters = [Expense.user_id == user_id]
        if search:
            like = f"%{search}%"
            filters.append(or_(Expense.description.ilike(like), Expense.category.ilike(like)))
        if category:
            filters.append(Expense.category == category)
        if trip_id is not None:
            filters.append(Expense.trip_id == trip_id)
        if source_type is not None:
            filters.append(Expense.source_type == source_type)
        if source_id is not None:
            filters.append(Expense.source_id == source_id)
        if date_from is not None:
            filters.append(Expense.occurred_at >= datetime.combine(date_from, time.min, tzinfo=UTC))
        if date_to is not None:
            filters.append(Expense.occurred_at <= datetime.combine(date_to, time.max, tzinfo=UTC))

        if sort == "oldest":
            order_by = (Expense.occurred_at.asc().nullslast(), Expense.created_at.asc())
        elif sort == "amount":
            order_by = (Expense.amount.desc(), Expense.created_at.desc())
        elif sort == "created":
            order_by = (Expense.created_at.desc(), Expense.id)
        else:  # newest
            order_by = (Expense.occurred_at.desc().nullslast(), Expense.created_at.desc())

        total = self.db.scalar(select(func.count()).select_from(Expense).where(*filters))
        stmt = (
            select(Expense)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def get(self, *, user_id: uuid.UUID, expense_id: uuid.UUID) -> Expense | None:
        return self.db.scalar(
            select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
        )

    def list_for_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.user_id == user_id, Expense.trip_id == trip_id)
            .order_by(Expense.occurred_at.asc().nullslast(), Expense.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_user(self, *, user_id: uuid.UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.user_id == user_id)
            .order_by(Expense.occurred_at.asc().nullslast(), Expense.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def create(self, expense: Expense) -> Expense:
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def save(self, expense: Expense, *, commit: bool = True) -> Expense:
        self.db.add(expense)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(expense)
        return expense

    def delete(self, expense: Expense, *, commit: bool = True) -> None:
        self.db.delete(expense)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

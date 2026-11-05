import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.user import utcnow
from app.repositories.expense import ExpenseRepository
from app.repositories.trip import TripRepository


class ExpenseNotFoundError(Exception):
    pass


class ExpenseTripAssignmentError(ExpenseNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class ExpenseService:
    """Expense CRUD, scoped by user and optionally linked into a trip (spec #19)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.expenses = ExpenseRepository(db)
        self.trips = TripRepository(db)

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise ExpenseTripAssignmentError

    def list_expenses(
        self,
        *,
        user_id: uuid.UUID,
        search: str | None = None,
        category: str | None = None,
        trip_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Expense], int]:
        return self.expenses.list(
            user_id=user_id,
            search=search,
            category=category,
            trip_id=trip_id,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def get_expense(self, *, user_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
        expense = self.expenses.get(user_id=user_id, expense_id=expense_id)
        if expense is None:
            raise ExpenseNotFoundError
        return expense

    def create_expense(self, *, user_id: uuid.UUID, payload) -> Expense:
        data = payload.model_dump()
        self._check_trip(user_id=user_id, trip_id=data.get("trip_id"))
        # A spend without a timestamp would sort to the very bottom of the
        # timeline; default to "now" so it lands where it was recorded.
        if data.get("occurred_at") is None:
            data["occurred_at"] = utcnow()
        expense = Expense(user_id=user_id, **data)
        return self.expenses.create(expense)

    def update_expense(self, *, user_id: uuid.UUID, expense_id: uuid.UUID, payload) -> Expense:
        expense = self.get_expense(user_id=user_id, expense_id=expense_id)
        data = payload.model_dump(exclude_unset=True)
        if "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])

        # amount/currency are NOT NULL; an explicit null must not wipe them.
        for required in ("amount", "currency"):
            if required in data and data[required] is None:
                data.pop(required)

        for field, value in data.items():
            setattr(expense, field, value)
        return self.expenses.save(expense)

    def delete_expense(self, *, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
        expense = self.get_expense(user_id=user_id, expense_id=expense_id)
        self.expenses.delete(expense)

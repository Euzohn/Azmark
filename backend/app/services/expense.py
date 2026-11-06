import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.expense import Expense
from app.models.hotel import Hotel
from app.models.transport_record import TransportRecord
from app.models.user import utcnow
from app.repositories.expense import ExpenseRepository
from app.repositories.trip import TripRepository
from app.schemas.expense import ExpenseCurrencyTotal, ExpenseSummary
from app.services.expense_source import SOURCE_ACTIVITY, SOURCE_HOTEL, SOURCE_TRANSPORT
from app.services.idempotency import IdempotencyResultGoneError, IdempotencyService

ZERO = Decimal("0")


def summarize_expenses(expenses: list[Expense], report_currency: str) -> ExpenseSummary:
    """Group spend into report-currency total + unconverted buckets (docs §6.6)."""
    total = ZERO
    converted_count = 0
    unconverted_count = 0
    buckets: dict[str, Decimal] = {}

    for expense in expenses:
        if expense.currency == report_currency:
            total += expense.amount
            converted_count += 1
        elif expense.converted_currency == report_currency and expense.converted_amount is not None:
            total += expense.converted_amount
            converted_count += 1
        else:
            buckets[expense.currency] = buckets.get(expense.currency, ZERO) + expense.amount
            unconverted_count += 1

    return ExpenseSummary(
        report_currency=report_currency,
        converted_total=total,
        converted_count=converted_count,
        unconverted_count=unconverted_count,
        unconverted=[
            ExpenseCurrencyTotal(currency=currency, amount=amount)
            for currency, amount in sorted(buckets.items())
        ],
    )


class ExpenseNotFoundError(Exception):
    pass


class ExpenseTripAssignmentError(ExpenseNotFoundError):
    """The target trip does not exist or belongs to another user (spec #3.3/#57)."""


class ExpenseSourceNotFoundError(ExpenseNotFoundError):
    """The linked record does not exist or belongs to another user."""


class ExpenseSourceTypeError(Exception):
    """The source link is incomplete or names an unsupported entity type."""


class ExpenseTripConflictError(Exception):
    """A bound expense cannot be assigned to a trip other than its source's."""


class InvalidExpenseAmountsError(Exception):
    """Conversion fields are incomplete or inconsistent after the update."""


_MISSING = object()


class ExpenseService:
    """Expense CRUD, scoped by user and optionally linked to a source record (spec #19)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.expenses = ExpenseRepository(db)
        self.trips = TripRepository(db)

    def _check_trip(self, *, user_id: uuid.UUID, trip_id: uuid.UUID | None) -> None:
        if trip_id is not None and self.trips.get(user_id=user_id, trip_id=trip_id) is None:
            raise ExpenseTripAssignmentError

    def _resolve_source(
        self, *, user_id: uuid.UUID, source_type: str, source_id: uuid.UUID
    ) -> uuid.UUID | None:
        """Return the source's current trip, or raise if it is not the user's.

        ``FOR UPDATE`` serializes binding against a concurrent source move or
        delete: otherwise the expense could keep the source's old trip (or a
        source that is being deleted) while the other transaction commits.
        """
        if source_type == SOURCE_TRANSPORT:
            model = TransportRecord
        elif source_type == SOURCE_HOTEL:
            model = Hotel
        elif source_type == SOURCE_ACTIVITY:
            model = Activity
        else:
            raise ExpenseSourceTypeError
        entity = self.db.scalar(
            select(model).where(model.id == source_id, model.user_id == user_id).with_for_update()
        )
        if entity is None:
            raise ExpenseSourceNotFoundError
        return entity.trip_id

    def _validate_amounts(self, state: dict) -> None:
        converted_amount = state.get("converted_amount")
        converted_currency = state.get("converted_currency")
        exchange_rate = state.get("exchange_rate")
        exchange_rate_date = state.get("exchange_rate_date")

        if (converted_amount is None) != (converted_currency is None):
            raise InvalidExpenseAmountsError
        if exchange_rate is not None and converted_amount is None:
            raise InvalidExpenseAmountsError
        if exchange_rate is not None and Decimal(str(exchange_rate)) <= 0:
            raise InvalidExpenseAmountsError
        if exchange_rate_date is not None and exchange_rate is None:
            raise InvalidExpenseAmountsError

    def list_expenses(
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
        return self.expenses.list(
            user_id=user_id,
            search=search,
            category=category,
            trip_id=trip_id,
            source_type=source_type,
            source_id=source_id,
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
        expense, _ = self.create_expense_idempotent(user_id=user_id, payload=payload)
        return expense

    def create_expense_idempotent(
        self,
        *,
        user_id: uuid.UUID,
        payload,
        idempotency_key: str | None = None,
        idempotency_operation: str = "create_expense",
    ) -> tuple[Expense, bool]:
        """Create an expense; ``replayed`` is true for an idempotent retry.

        The record-detail "add expense" flow can be retried by the browser or a
        mobile network without writing the same spend twice (docs §4.3).
        """
        idem = IdempotencyService(self.db)
        replay, record, _ = idem.begin(
            user_id=user_id,
            operation=idempotency_operation,
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
        )
        if replay is not None:
            expense = (
                self.expenses.get(user_id=user_id, expense_id=replay.resource_id)
                if replay.resource_id is not None
                else None
            )
            if expense is None:
                raise IdempotencyResultGoneError
            return expense, True

        data = payload.model_dump()
        source_type = data.get("source_type")
        source_id = data.get("source_id")

        if (source_type is None) != (source_id is None):
            raise ExpenseSourceTypeError

        if source_type is not None:
            derived_trip = self._resolve_source(
                user_id=user_id, source_type=source_type, source_id=source_id
            )
            requested = data.get("trip_id")
            if requested is not None and requested != derived_trip:
                raise ExpenseTripConflictError
            data["trip_id"] = derived_trip
        else:
            self._check_trip(user_id=user_id, trip_id=data.get("trip_id"))

        self._validate_amounts(data)

        # A spend without a timestamp would sort to the very bottom of the
        # timeline; default to "now" so it lands where it was recorded.
        if data.get("occurred_at") is None:
            data["occurred_at"] = utcnow()
        expense = Expense(user_id=user_id, **data)
        self.db.add(expense)
        self.db.flush()
        idem.complete(
            record,
            resource_id=expense.id,
            response={"id": str(expense.id), "amount": str(expense.amount)},
        )
        # One commit keeps the row and the idempotency result atomic.
        self.db.commit()
        self.db.refresh(expense)
        return expense, False

    def update_expense(self, *, user_id: uuid.UUID, expense_id: uuid.UUID, payload) -> Expense:
        expense = self.get_expense(user_id=user_id, expense_id=expense_id)
        data = payload.model_dump(exclude_unset=True)

        # amount/currency are NOT NULL; an explicit null must not wipe them.
        for required in ("amount", "currency"):
            if required in data and data[required] is None:
                data.pop(required)

        source_touched = "source_type" in data or "source_id" in data
        if source_touched:
            source_type = data.get("source_type", _MISSING)
            source_id = data.get("source_id", _MISSING)
            if source_type is _MISSING:
                source_type = expense.source_type
            if source_id is _MISSING:
                source_id = expense.source_id
            if (source_type is None) != (source_id is None):
                raise ExpenseSourceTypeError

            if source_type is None:
                # Explicit unbind keeps the current trip unless the caller
                # provides another valid one.
                data["source_type"] = None
                data["source_id"] = None
                if "trip_id" in data:
                    self._check_trip(user_id=user_id, trip_id=data["trip_id"])
            else:
                derived_trip = self._resolve_source(
                    user_id=user_id, source_type=source_type, source_id=source_id
                )
                requested = data.get("trip_id", _MISSING)
                if requested is not _MISSING and requested != derived_trip:
                    raise ExpenseTripConflictError
                data["source_type"] = source_type
                data["source_id"] = source_id
                data["trip_id"] = derived_trip
        elif expense.source_type is not None and "trip_id" in data:
            # A bound expense derives its trip; an explicit value must agree.
            derived_trip = self._resolve_source(
                user_id=user_id,
                source_type=expense.source_type,
                source_id=expense.source_id,  # type: ignore[arg-type]
            )
            if data["trip_id"] != derived_trip:
                raise ExpenseTripConflictError
            data["trip_id"] = derived_trip
        elif "trip_id" in data:
            self._check_trip(user_id=user_id, trip_id=data["trip_id"])

        # Changing the original amount/currency invalidates an old conversion
        # unless the caller supplies conversion fields in the same request.
        conversion_fields = {
            "converted_amount",
            "converted_currency",
            "exchange_rate",
            "exchange_rate_date",
        }
        amount_changed = "amount" in data or "currency" in data
        if amount_changed and not (conversion_fields & data.keys()):
            data.update(
                converted_amount=None,
                converted_currency=None,
                exchange_rate=None,
                exchange_rate_date=None,
            )

        merged = {
            "amount": expense.amount,
            "currency": expense.currency,
            "converted_amount": expense.converted_amount,
            "converted_currency": expense.converted_currency,
            "exchange_rate": expense.exchange_rate,
            "exchange_rate_date": expense.exchange_rate_date,
            **{key: value for key, value in data.items() if key in conversion_fields},
        }
        self._validate_amounts(merged)

        for field, value in data.items():
            setattr(expense, field, value)
        return self.expenses.save(expense)

    def delete_expense(self, *, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
        expense = self.get_expense(user_id=user_id, expense_id=expense_id)
        self.expenses.delete(expense)

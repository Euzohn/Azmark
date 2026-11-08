import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Spend buckets are a small, stable vocabulary so the UI can sum by category.
# The DB column stays a permissive String(40) for future/imported values.
ExpenseCategory = Literal[
    "transport",
    "accommodation",
    "food",
    "shopping",
    "entertainment",
    "other",
]

EXPENSE_CATEGORIES: tuple[str, ...] = (
    "transport",
    "accommodation",
    "food",
    "shopping",
    "entertainment",
    "other",
)

# Entity vocabulary (docs/data-model.md §3.1). A transport record's own type
# still says flight/train/other; the link only names the entity kind.
ExpenseSourceType = Literal["transport", "hotel", "activity"]


def _upper_currency(value: str | None) -> str | None:
    return value.strip().upper() if isinstance(value, str) else value


class ExpenseBase(BaseModel):
    category: ExpenseCategory = "other"
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    converted_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    converted_currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=8)
    exchange_rate_date: date | None = None
    occurred_at: datetime | None = None
    description: str | None = None
    trip_id: uuid.UUID | None = None
    source_type: ExpenseSourceType | None = None
    source_id: uuid.UUID | None = None

    @field_validator("currency", "converted_currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return _upper_currency(value)

    @model_validator(mode="after")
    def _check_source_pair(self) -> "ExpenseBase":
        if (self.source_type is None) != (self.source_id is None):
            raise ValueError("source_type and source_id must be provided together")
        return self


class ExpenseCreate(ExpenseBase):
    @model_validator(mode="after")
    def _check_conversion(self) -> "ExpenseCreate":
        if (self.converted_amount is None) != (self.converted_currency is None):
            raise ValueError("converted_amount and converted_currency must be provided together")
        if self.exchange_rate is not None and self.converted_amount is None:
            raise ValueError("exchange_rate requires converted_amount and converted_currency")
        if self.exchange_rate is not None and self.exchange_rate <= 0:
            raise ValueError("exchange_rate must be greater than zero")
        return self


class ExpenseUpdate(BaseModel):
    category: ExpenseCategory | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    converted_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    converted_currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=8)
    exchange_rate_date: date | None = None
    occurred_at: datetime | None = None
    description: str | None = None
    trip_id: uuid.UUID | None = None
    source_type: ExpenseSourceType | None = None
    source_id: uuid.UUID | None = None

    @field_validator("currency", "converted_currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return _upper_currency(value)


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ExpenseList(BaseModel):
    items: list[ExpenseRead]
    total: int
    page: int
    page_size: int


class ExpenseCurrencyTotal(BaseModel):
    currency: str
    amount: Decimal


class ExpenseSummary(BaseModel):
    """Trip spend in the user's report currency (docs §6.6).

    Expenses in another currency without a matching conversion are reported
    separately instead of being added to the total.
    """

    report_currency: str
    converted_total: Decimal
    converted_count: int
    unconverted_count: int
    unconverted: list[ExpenseCurrencyTotal]


class ExpenseBreakdownItem(BaseModel):
    """One spend bucket normalised to the report currency.

    ``amount`` only sums the expenses that could be converted; ``count`` is how
    many contributed to it and ``unconverted_count`` how many were left out,
    so the UI can flag a bucket whose amount understates what was really spent
    instead of silently dropping the remainder.
    """

    label: str
    name: str | None = None
    amount: Decimal
    count: int
    unconverted_count: int = 0


class ExpenseCurrencyBreakdown(BaseModel):
    """Original-currency total plus the portion that is convertible."""

    currency: str
    amount: Decimal
    count: int
    converted_amount: Decimal | None = None
    converted_currency: str | None = None


class ExpenseStatistics(BaseModel):
    """Whole-history spend aggregates for the statistics page (spec #28)."""

    report_currency: str
    total: Decimal
    count: int
    converted_count: int
    unconverted_count: int
    average: Decimal
    largest: Decimal
    by_category: list[ExpenseBreakdownItem]
    by_month: list[ExpenseBreakdownItem]
    by_year: list[ExpenseBreakdownItem]
    by_source_type: list[ExpenseBreakdownItem]
    by_trip: list[ExpenseBreakdownItem]
    by_currency: list[ExpenseCurrencyBreakdown]
    unconverted: list[ExpenseCurrencyTotal]

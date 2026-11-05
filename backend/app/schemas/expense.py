import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

    @field_validator("currency", "converted_currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return _upper_currency(value)


class ExpenseCreate(ExpenseBase):
    pass


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

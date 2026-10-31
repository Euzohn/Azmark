import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

TokenName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AccessTokenCreate(BaseModel):
    name: TokenName
    scope: Literal["read", "write"] = "read"
    # Default 90 days; an explicit null creates a non-expiring token.
    expires_in_days: int | None = Field(default=90, ge=1, le=3650)


class AccessTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    scope: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class AccessTokenCreated(AccessTokenRead):
    """Carries the plaintext secret; only this response ever contains it."""

    token: str


class AccessTokenList(BaseModel):
    items: list[AccessTokenRead]

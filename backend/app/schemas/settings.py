from pydantic import BaseModel, Field


class ProviderKeyWrite(BaseModel):
    api_key: str = Field(min_length=1, max_length=256)


class ProviderKeyStatus(BaseModel):
    provider: str
    configured: bool


class ProviderKeysRead(BaseModel):
    providers: list[ProviderKeyStatus]


class StorageUsageRead(BaseModel):
    """User-facing storage usage; ``quota_bytes`` 0 means unlimited."""

    used_bytes: int
    quota_bytes: int
    unlimited: bool

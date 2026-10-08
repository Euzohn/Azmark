from pydantic import BaseModel, Field


class ProviderKeyWrite(BaseModel):
    api_key: str = Field(min_length=1, max_length=256)


class ProviderKeyStatus(BaseModel):
    provider: str
    configured: bool


class ProviderKeysRead(BaseModel):
    providers: list[ProviderKeyStatus]

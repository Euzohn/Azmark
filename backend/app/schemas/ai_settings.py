from pydantic import BaseModel, Field


class AiSettingsWrite(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=256)
    temperature: float | None = Field(default=None, ge=0, le=2)
    context_limit: int | None = Field(default=None, ge=1000)
    web_search: bool | None = None


class AiSettingsRead(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    configured: bool
    temperature: float | None = None
    context_limit: int | None = None
    web_search: bool = False

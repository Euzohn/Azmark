from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.url_guard import validate_base_url


class AiSettingsWrite(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=256)
    temperature: float | None = Field(default=None, ge=0, le=2)
    context_limit: int | None = Field(default=None, ge=1000)

    @field_validator("base_url")
    @classmethod
    def _guard_base_url(cls, value: str | None) -> str | None:
        """The server requests this URL with httpx; keep it public-reachable (spec #70)."""
        if value is None:
            return None
        return validate_base_url(value, allow_private=settings.allow_private_base_urls)


class AiSettingsRead(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    configured: bool
    temperature: float | None = None
    context_limit: int | None = None

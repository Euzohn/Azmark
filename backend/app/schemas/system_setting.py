"""Admin system-settings API models (spec #5, #78)."""

from typing import Literal

from pydantic import BaseModel, Field


class AdminSettingsRead(BaseModel):
    """Masked view: SMTP password and Turnstile secret are reported only as ``is set``."""

    allow_registration: bool
    registration_captcha_enabled: bool
    captcha_provider: str
    turnstile_site_key: str | None
    turnstile_secret_set: bool
    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    smtp_sender: str | None
    smtp_starttls: bool
    smtp_password_set: bool


class AdminSettingsUpdate(BaseModel):
    allow_registration: bool | None = None
    registration_captcha_enabled: bool | None = None
    # "arithmetic" (self-hosted default) or "turnstile" (Cloudflare).
    captcha_provider: Literal["arithmetic", "turnstile"] | None = None
    turnstile_site_key: str | None = Field(default=None, max_length=255)
    # Write-only, like smtp_password: empty/omitted keeps the stored value.
    turnstile_secret: str | None = Field(default=None, max_length=255)
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=255)
    smtp_sender: str | None = Field(default=None, max_length=255)
    smtp_starttls: bool | None = None


class AdminTestEmailRequest(BaseModel):
    to: str | None = Field(default=None, max_length=255)


class AdminTestEmailResponse(BaseModel):
    ok: bool

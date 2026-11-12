import uuid

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=100)
    # Captcha challenge (spec #60). Required only while the instance has the
    # registration captcha enabled; ignored (and optional) otherwise.
    captcha_token: str | None = Field(default=None, max_length=512)
    captcha_answer: str | None = Field(default=None, max_length=16)


class AuthConfig(BaseModel):
    """Public facts the unauthenticated login/register pages need to render
    correctly: whether self-registration is open, how bots are challenged, and
    the Turnstile site key when the widget must render."""

    allow_registration: bool
    registration_captcha_enabled: bool
    captcha_provider: str
    turnstile_site_key: str | None


class CaptchaChallenge(BaseModel):
    token: str
    question: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None
    display_name: str | None
    role: str
    locale: str
    timezone: str
    currency: str


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    locale: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, max_length=3)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UsernameChange(BaseModel):
    new_username: str = Field(min_length=3, max_length=64)
    current_password: str


class DeleteAccountRequest(BaseModel):
    """Password confirmation for the destructive action (spec #48)."""

    password: str

"""Instance-wide system settings, admin-editable at runtime.

A single row (id=1) holds registration policy, the registration captcha switch
and SMTP credentials for outbound email. Seeded by migration 0032 with secure
defaults: self-registration off, captcha off. Secrets (``smtp_password_enc``)
are Fernet-encrypted with a key derived from SECRET_KEY — see
``app.core.security.encrypt_field`` — and are never returned by the API.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow

# Fernet salt namespace, distinct per secret domain so ciphertexts cannot be
# replayed across fields.
SMTP_PASSWORD_SALT = "smtp-password"
TURNSTILE_SECRET_SALT = "turnstile-secret"


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Policy: close the door by default; admins open it explicitly.
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registration_captcha_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Bot protection provider: "arithmetic" (self-hosted, zero dependency) or
    # "turnstile" (Cloudflare). The server falls back to arithmetic while
    # Turnstile is not fully configured — site key or secret missing — so the
    # public form and the register endpoint always agree on the challenge.
    captcha_provider: Mapped[str] = mapped_column(String(20), default="arithmetic", nullable=False)
    turnstile_site_key: Mapped[str | None] = mapped_column(String(255))
    turnstile_secret_key_enc: Mapped[str | None] = mapped_column(String(512))
    # Outbound email (SMTP). Only consumed by the admin test-send for now;
    # verification / recovery flows later reuse the same configuration.
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password_enc: Mapped[str | None] = mapped_column(String(512))
    smtp_sender: Mapped[str | None] = mapped_column(String(255))
    smtp_starttls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

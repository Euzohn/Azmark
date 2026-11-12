"""Instance-wide system settings: one row, admin-editable at runtime.

Covers registration policy (self-registration on/off, arithmetic captcha) and
outbound email (SMTP) configuration. Single-row by design: settings are
global, not per-tenant — a simple PK lookup per request, no cache invalidation
to get wrong.

Security notes (spec #45, #96):
- the SMTP password is Fernet-encrypted at rest and never returned by the API
- no secret ever reaches the audit log — only field *names* are stored
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.captcha import CAPTCHA_PROVIDER_ARITHMETIC, CAPTCHA_PROVIDER_TURNSTILE
from app.core.security import decrypt_field, encrypt_field
from app.models.system_setting import (
    SMTP_PASSWORD_SALT,
    TURNSTILE_SECRET_SALT,
    SystemSetting,
)
from app.schemas.system_setting import (
    AdminSettingsRead,
    AdminSettingsUpdate,
)

SETTINGS_ROW_ID = 1


def effective_registration_captcha(row: SystemSetting) -> tuple[str, str | None, str]:
    """(provider, site_key, secret) that the register flow actually enforces.

    Turnstile is effective only when it is selected *and* fully configured —
    a decryptable secret plus a site key (the widget cannot render without
    one). Any half-configured state falls back to the arithmetic challenge,
    so ``/auth/config`` and ``/auth/register`` always agree on which
    challenge the visitor is answering.
    """
    if row.captcha_provider == CAPTCHA_PROVIDER_TURNSTILE and row.turnstile_site_key:
        secret = decrypt_field(TURNSTILE_SECRET_SALT, row.turnstile_secret_key_enc or "")
        if secret:
            return CAPTCHA_PROVIDER_TURNSTILE, row.turnstile_site_key, secret
    return CAPTCHA_PROVIDER_ARITHMETIC, None, ""


class SmtpDeliveryError(Exception):
    """Outbound SMTP failed; the message is safe to show in the admin UI."""


class SystemSettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self) -> SystemSetting:
        row = self.db.get(SystemSetting, SETTINGS_ROW_ID)
        if row is None:
            # Secure defaults mirror the model: registration closed, captcha off.
            row = SystemSetting(id=SETTINGS_ROW_ID)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def read(self) -> AdminSettingsRead:
        row = self.get_or_create()
        return AdminSettingsRead(
            allow_registration=row.allow_registration,
            registration_captcha_enabled=row.registration_captcha_enabled,
            captcha_provider=row.captcha_provider,
            turnstile_site_key=row.turnstile_site_key,
            turnstile_secret_set=bool(row.turnstile_secret_key_enc),
            smtp_host=row.smtp_host,
            smtp_port=row.smtp_port,
            smtp_username=row.smtp_username,
            smtp_sender=row.smtp_sender,
            smtp_starttls=row.smtp_starttls,
            smtp_password_set=bool(row.smtp_password_enc),
        )

    def update(self, payload: AdminSettingsUpdate) -> AdminSettingsRead:
        row = self.get_or_create()
        data = payload.model_dump(exclude_unset=True)
        password = data.pop("smtp_password", None)
        turnstile_secret = data.pop("turnstile_secret", None)
        for field, value in data.items():
            # Omitted (never in data) = untouched. Explicit ``None`` clears
            # optional text fields; booleans and the provider with None mean
            # "leave as is".
            if value is None and field in (
                "allow_registration",
                "registration_captcha_enabled",
                "captcha_provider",
                "smtp_starttls",
            ):
                continue
            setattr(row, field, value)
        if password:
            row.smtp_password_enc = encrypt_field(SMTP_PASSWORD_SALT, password)
        if turnstile_secret:
            row.turnstile_secret_key_enc = encrypt_field(TURNSTILE_SECRET_SALT, turnstile_secret)
        self.db.commit()
        self.db.refresh(row)
        return self.read()

    def send_test_email(self, to: str) -> None:
        row = self.get_or_create()
        if not row.smtp_host or not row.smtp_sender:
            raise SmtpDeliveryError("SMTP server and sender must be configured first")

        message = EmailMessage()
        message["From"] = row.smtp_sender
        message["To"] = to
        message["Subject"] = "Azmark SMTP test"
        message.set_content(
            "This is a test message from your Azmark instance. "
            "If you are reading it, outbound email is configured correctly."
        )

        try:
            with smtplib.SMTP(row.smtp_host, row.smtp_port or 587, timeout=15) as server:
                server.ehlo()
                if row.smtp_starttls:
                    server.starttls()
                    server.ehlo()
                if row.smtp_username:
                    password = decrypt_field(SMTP_PASSWORD_SALT, row.smtp_password_enc or "")
                    server.login(row.smtp_username, password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise SmtpDeliveryError(str(exc)) from exc

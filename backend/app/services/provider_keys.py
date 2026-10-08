"""Encrypted per-user provider API keys (spec #35, #45, #66).

Keys are Fernet-encrypted at rest; the API only ever returns whether a key is
configured, never the key itself.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_value, encrypt_value
from app.models.provider_setting import ProviderSetting


class ProviderKeyStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _find(self, *, user_id: uuid.UUID, provider: str) -> ProviderSetting | None:
        return self.db.scalar(
            select(ProviderSetting).where(
                ProviderSetting.user_id == user_id,
                ProviderSetting.provider == provider,
            )
        )

    def upsert(self, *, user_id: uuid.UUID, provider: str, api_key: str) -> None:
        setting = self._find(user_id=user_id, provider=provider)
        if setting is None:
            setting = ProviderSetting(user_id=user_id, provider=provider)
            self.db.add(setting)
        setting.encrypted_value = encrypt_value(api_key)
        self.db.commit()

    def get_decrypted(self, *, user_id: uuid.UUID) -> dict[str, str]:
        """Return provider -> raw key, skipping any that fail to decrypt."""
        rows = self.db.scalars(select(ProviderSetting).where(ProviderSetting.user_id == user_id))
        result: dict[str, str] = {}
        for row in rows:
            raw = decrypt_value(row.encrypted_value)
            if raw:
                result[row.provider] = raw
        return result

    def delete(self, *, user_id: uuid.UUID, provider: str) -> bool:
        setting = self._find(user_id=user_id, provider=provider)
        if setting is None:
            return False
        self.db.delete(setting)
        self.db.commit()
        return True

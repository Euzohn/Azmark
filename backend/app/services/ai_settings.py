"""Per-user LLM settings storage (spec #35, #36). Key encrypted at rest."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_value
from app.models.ai_setting import UserAiSetting
from app.schemas.ai_settings import AiSettingsRead, AiSettingsWrite


class AiSettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _find(self, *, user_id: uuid.UUID) -> UserAiSetting | None:
        return self.db.scalar(select(UserAiSetting).where(UserAiSetting.user_id == user_id))

    def get(self, *, user_id: uuid.UUID) -> AiSettingsRead:
        setting = self._find(user_id=user_id)
        if setting is None:
            return AiSettingsRead(provider="", model="", configured=False)
        return AiSettingsRead(
            provider=setting.provider,
            model=setting.model,
            base_url=setting.base_url,
            configured=bool(setting.api_key_enc),
            temperature=setting.temperature,
            context_limit=setting.context_limit,
            web_search=setting.web_search,
        )

    def upsert(self, *, user_id: uuid.UUID, payload: AiSettingsWrite) -> AiSettingsRead:
        setting = self._find(user_id=user_id)
        if setting is None:
            setting = UserAiSetting(user_id=user_id)
            self.db.add(setting)
        setting.provider = payload.provider
        setting.model = payload.model
        setting.base_url = payload.base_url
        if payload.api_key:
            setting.api_key_enc = encrypt_value(payload.api_key)
        if payload.temperature is not None:
            setting.temperature = payload.temperature
        if payload.context_limit is not None:
            setting.context_limit = payload.context_limit
        if payload.web_search is not None:
            setting.web_search = payload.web_search
        self.db.commit()
        return self.get(user_id=user_id)

    def delete(self, *, user_id: uuid.UUID) -> bool:
        setting = self._find(user_id=user_id)
        if setting is None:
            return False
        self.db.delete(setting)
        self.db.commit()
        return True

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import access_token_prefix, generate_access_token, hash_access_token
from app.models.personal_access_token import PersonalAccessToken, TokenScope
from app.models.user import User, UserStatus, utcnow

# Writing ``last_used_at`` on every request would turn reads into writes; once
# a minute is precise enough for the settings page.
_LAST_USED_THROTTLE = timedelta(seconds=60)


class AccessTokenNotFoundError(Exception):
    """Unknown token id, or a token owned by another user (spec #57)."""


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes for timezone-aware columns."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AccessTokenService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, *, user_id: uuid.UUID) -> list[PersonalAccessToken]:
        stmt = (
            select(PersonalAccessToken)
            .where(PersonalAccessToken.user_id == user_id)
            .order_by(PersonalAccessToken.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        scope: str = TokenScope.READ,
        expires_in_days: int | None = 90,
    ) -> tuple[PersonalAccessToken, str]:
        """Persist the digest and return the plaintext secret exactly once."""
        if scope not in TokenScope.ALL:
            raise ValueError(f"Unknown scope: {scope}")
        secret = generate_access_token()
        record = PersonalAccessToken(
            user_id=user_id,
            name=name,
            token_prefix=access_token_prefix(secret),
            token_hash=hash_access_token(secret),
            scope=scope,
            expires_at=(
                utcnow() + timedelta(days=expires_in_days) if expires_in_days is not None else None
            ),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record, secret

    def _get(self, *, user_id: uuid.UUID, token_id: uuid.UUID) -> PersonalAccessToken:
        record = self.db.scalar(
            select(PersonalAccessToken).where(
                PersonalAccessToken.id == token_id,
                PersonalAccessToken.user_id == user_id,
            )
        )
        if record is None:
            raise AccessTokenNotFoundError(str(token_id))
        return record

    def revoke(self, *, user_id: uuid.UUID, token_id: uuid.UUID) -> PersonalAccessToken:
        record = self._get(user_id=user_id, token_id=token_id)
        if record.revoked_at is None:
            record.revoked_at = utcnow()
            self.db.commit()
            self.db.refresh(record)
        return record

    def delete(self, *, user_id: uuid.UUID, token_id: uuid.UUID) -> None:
        record = self._get(user_id=user_id, token_id=token_id)
        self.db.delete(record)
        self.db.commit()

    def authenticate(self, presented: str) -> tuple[User, PersonalAccessToken] | None:
        """Resolve a bearer secret to its owner, or ``None`` when unusable."""
        record = self.db.scalar(
            select(PersonalAccessToken).where(
                PersonalAccessToken.token_hash == hash_access_token(presented)
            )
        )
        if record is None or record.revoked_at is not None:
            return None

        now = utcnow()
        if record.expires_at is not None and _as_utc(record.expires_at) <= now:
            return None

        user = self.db.get(User, record.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            return None

        if record.last_used_at is None or now - _as_utc(record.last_used_at) >= _LAST_USED_THROTTLE:
            record.last_used_at = now
            self.db.commit()

        return user, record

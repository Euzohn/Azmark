from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.ai_setting import UserAiSetting
from app.models.audit_log import AuditLog
from app.models.provider_setting import ProviderSetting
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.user import User, UserRole, UserStatus


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def count_active_admins(self) -> int:
        total = self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE)
        )
        return int(total or 0)

    def delete_account(self, user: User) -> None:
        """Delete a user and all owned data (spec #48).

        Done explicitly instead of relying on ON DELETE CASCADE so the same
        behaviour holds on SQLite (tests) and PostgreSQL. Audit history is kept
        but anonymised by clearing ``user_id`` (spec #48).
        """
        self.db.execute(update(AuditLog).where(AuditLog.user_id == user.id).values(user_id=None))
        # Stored files are not implemented yet (spec #44); once Attachment and
        # StorageProvider land, their rows/objects must be removed here too.
        self.db.execute(delete(TransportRecord).where(TransportRecord.user_id == user.id))
        self.db.execute(delete(Trip).where(Trip.user_id == user.id))
        self.db.execute(delete(UserAiSetting).where(UserAiSetting.user_id == user.id))
        self.db.execute(delete(ProviderSetting).where(ProviderSetting.user_id == user.id))
        self.db.delete(user)
        self.db.commit()

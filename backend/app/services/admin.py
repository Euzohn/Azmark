"""Admin bootstrap and administration (spec #5, #58, #78).

Admins operate across users, but only through the endpoints in
``app/api/routes/admin.py``; every other query stays scoped by ``user_id``.
"""

from __future__ import annotations

import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.user import User, UserRole, UserStatus
from app.repositories.user import UserRepository
from app.schemas.admin import AdminSystemRead, AdminUserRead, AdminUserUpdate


class AdminUserNotFoundError(Exception):
    pass


class AdminSelfLockoutError(Exception):
    """An admin tried to demote or disable their own account."""


class AdminBootstrapError(Exception):
    pass


def _username_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip().lower()
    username = re.sub(r"[^a-z0-9_.-]", "", local)
    if len(username) < 3:
        username = f"{username}admin" if username else "admin"
    return username[:64]


def ensure_admin(
    db: Session,
    *,
    username: str,
    email: str | None = None,
    password: str | None = None,
    reset_password: bool = False,
) -> tuple[User, str]:
    """Create an admin, or promote an existing account.

    Returns ``(user, outcome)`` where outcome is one of ``created``,
    ``promoted``, ``updated`` or ``exists``. Passwords are only written when
    creating or when ``reset_password`` is requested so repeated bootstraps do
    not silently reset a working credential.
    """
    username = username.strip()
    if not username:
        raise AdminBootstrapError("username is required")
    email = email.strip() if email else None

    if reset_password and not password:
        raise AdminBootstrapError("password is required to reset it")

    repo = UserRepository(db)
    existing = repo.get_by_username(username)
    if existing is None and email:
        existing = repo.get_by_email(email)

    if existing is not None:
        changed = False
        promoted = False
        if existing.role != UserRole.ADMIN:
            existing.role = UserRole.ADMIN
            promoted = True
            changed = True
        if email and existing.email != email:
            existing.email = email
            changed = True
        if reset_password and password:
            existing.password_hash = hash_password(password)
            changed = True
            return repo.save(existing), "updated"
        if changed:
            return repo.save(existing), "promoted" if promoted else "updated"
        return existing, "exists"

    if not password:
        raise AdminBootstrapError("password is required to create an admin")
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        display_name=username,
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    return repo.create(user), "created"


def bootstrap_admin_from_env() -> bool:
    """Create the first admin from ADMIN_EMAIL/ADMIN_PASSWORD (spec #78).

    No-op unless both are configured and no active admin exists yet. Called on
    application startup; safe to run on every boot.
    """
    email = settings.admin_email.strip()
    password = settings.admin_password
    if not email or not password:
        return False

    username = settings.admin_username.strip() or _username_from_email(email)
    with SessionLocal() as db:
        has_admin = db.scalar(
            select(User.id)
            .where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE)
            .limit(1)
        )
        if has_admin is not None:
            return False
        ensure_admin(db, username=username, email=email, password=password, reset_password=True)
        return True


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AdminUserRead], int]:
        conditions = []
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.display_name.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(User)
        stmt = select(User)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            stmt = stmt.where(condition)

        total = self.db.scalar(count_stmt)
        users = list(
            self.db.scalars(
                stmt.order_by(User.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        if not users:
            return [], int(total or 0)

        ids = [user.id for user in users]
        record_counts = dict(
            self.db.execute(
                select(TransportRecord.user_id, func.count())
                .where(TransportRecord.user_id.in_(ids))
                .group_by(TransportRecord.user_id)
            ).all()
        )
        trip_counts = dict(
            self.db.execute(
                select(Trip.user_id, func.count())
                .where(Trip.user_id.in_(ids))
                .group_by(Trip.user_id)
            ).all()
        )

        items = [
            AdminUserRead(
                id=user.id,
                username=user.username,
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                status=user.status,
                records=int(record_counts.get(user.id, 0)),
                trips=int(trip_counts.get(user.id, 0)),
                created_at=user.created_at,
            )
            for user in users
        ]
        return items, int(total or 0)

    def read_user(self, user: User) -> AdminUserRead:
        records = self.db.scalar(
            select(func.count())
            .select_from(TransportRecord)
            .where(TransportRecord.user_id == user.id)
        )
        trips = self.db.scalar(
            select(func.count()).select_from(Trip).where(Trip.user_id == user.id)
        )
        return AdminUserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            status=user.status,
            records=int(records or 0),
            trips=int(trips or 0),
            created_at=user.created_at,
        )

    def update_user(
        self, *, actor: User, user_id, payload: AdminUserUpdate
    ) -> tuple[AdminUserRead, list[str]]:
        user = self.db.get(User, user_id)
        if user is None:
            raise AdminUserNotFoundError

        data = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not data:
            return self.read_user(user), []

        if user.id == actor.id:
            if data.get("role") == UserRole.USER or data.get("status") == UserStatus.DISABLED:
                raise AdminSelfLockoutError

        for field, value in data.items():
            setattr(user, field, value)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self.read_user(user), sorted(data.keys())

    def system(self) -> AdminSystemRead:
        def count(model) -> int:
            return int(self.db.scalar(select(func.count()).select_from(model)) or 0)

        active_users = int(
            self.db.scalar(
                select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE)
            )
            or 0
        )
        admins = int(
            self.db.scalar(
                select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
            )
            or 0
        )
        return AdminSystemRead(
            version=settings.app_version,
            users=count(User),
            active_users=active_users,
            admins=admins,
            records=count(TransportRecord),
            trips=count(Trip),
            audit_logs=count(AuditLog),
        )

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository


class AuthError(Exception):
    pass


class UsernameTakenError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class AuthService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def register(
        self,
        *,
        username: str,
        password: str,
        email: str | None = None,
        display_name: str | None = None,
    ) -> User:
        if self.users.get_by_username(username) is not None:
            raise UsernameTakenError(username)
        user = User(
            username=username,
            password_hash=hash_password(password),
            email=email,
            display_name=display_name or username,
        )
        return self.users.create(user)

    def authenticate(self, *, username: str, password: str) -> User:
        user = self.users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        return user

    def change_password(self, *, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError
        user.password_hash = hash_password(new_password)
        return self.users.save(user)

    def change_username(self, *, user: User, current_password: str, new_username: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError
        existing = self.users.get_by_username(new_username)
        if existing is not None and existing.id != user.id:
            raise UsernameTakenError(new_username)
        user.username = new_username
        return self.users.save(user)

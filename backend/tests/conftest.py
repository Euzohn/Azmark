from collections.abc import Generator
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_storage_provider
from app.core.db import Base, get_db
from app.core.rate_limit import login_limiter, register_limiter
from app.main import app
from app.models.system_setting import SystemSetting
from app.services.storage import StorageObjectNotFound, StorageProvider

TEST_DATABASE_URL = "sqlite+pysqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def _reset_auth_rate_limiters() -> None:
    # The auth-route buckets are keyed by client IP; every TestClient request
    # shares "testclient", so clear the in-process windows between tests.
    login_limiter.reset()
    register_limiter.reset()


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> None:
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    # SQLite's legacy transaction mode does not BEGIN for reads. Start a real
    # outer transaction before creating the request-session savepoint so that
    # session commits and rollbacks stay isolated to this test.
    connection.exec_driver_sql("BEGIN")
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


class FakeStorageProvider(StorageProvider):
    """In-memory S3 stand-in so tests never need MinIO (see AGENTS.md)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    def put(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data
        self.content_types[key] = content_type

    def get(self, *, key: str) -> bytes:
        if key not in self.objects:
            raise StorageObjectNotFound("missing")
        return self.objects[key]

    def delete(self, *, key: str) -> None:
        self.objects.pop(key, None)
        self.content_types.pop(key, None)


def seed_system_settings(db: Session, **overrides) -> SystemSetting:
    """Upsert the single settings row within the current test transaction.

    The product default is registration-closed; the suite opts every test into
    the open-registration mode it was written against (tests that exercise the
    gate flip it back explicitly).
    """
    row = db.get(SystemSetting, 1)
    if row is None:
        row = SystemSetting(id=1, allow_registration=True)
        db.add(row)
    for field, value in overrides.items():
        setattr(row, field, value)
    db.flush()
    return row


@pytest.fixture
def storage() -> FakeStorageProvider:
    return FakeStorageProvider()


@pytest.fixture
def client(
    db: Session, storage: FakeStorageProvider, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_provider] = lambda: storage

    # Self-registration is closed by default (product decision); the test
    # suite opts into the open mode unless a test overrides it via
    # seed_system_settings(...).
    seed_system_settings(db)

    # The MCP endpoint is a raw ASGI mount, so it cannot use get_db; point its
    # session scope at the same in-memory session.
    from app.mcp import db as mcp_db

    monkeypatch.setattr(mcp_db, "session_scope", lambda: nullcontext(db))

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str, password: str = "secret123") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

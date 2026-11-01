"""Database handle for the MCP transport.

The MCP endpoint is a raw ASGI app mounted outside FastAPI's dependency graph,
so ``get_db`` never runs for it. Tests replace ``session_scope`` with an
in-memory session (see ``tests/conftest.py``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.db import SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Open a short-lived session for one MCP tool call."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

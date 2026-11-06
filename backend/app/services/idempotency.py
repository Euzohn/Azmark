"""User-scoped idempotency for retried mutating requests (docs §4.3, §9.1).

A network retry or an agent confirmation must not create the same visit twice.
The caller stores a request hash and, once the business row exists, the result
id, all in the same transaction. Concurrent duplicates are arbitrated by the
``(user_id, operation, key)`` unique constraint.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency_key import IdempotencyKey

TTL = timedelta(days=90)


class IdempotencyConflictError(Exception):
    """The key was already used for a different request."""


class IdempotencyResultGoneError(Exception):
    """The stored result was deleted before its key expired."""


class IdempotencyInProgressError(Exception):
    """A concurrent request with the same key has not finished yet."""


def request_digest(payload: dict[str, Any]) -> str:
    normalized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class IdempotencyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get(self, *, user_id: uuid.UUID, operation: str, key: str) -> IdempotencyKey | None:
        return self.db.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.operation == operation,
                IdempotencyKey.key == key,
            )
        )

    def begin(
        self,
        *,
        user_id: uuid.UUID,
        operation: str,
        key: str | None,
        payload: dict[str, Any],
    ) -> tuple[IdempotencyKey | None, IdempotencyKey | None, str]:
        """Reserve a key and report whether this request should write.

        Returns ``(replay, record, digest)``: a non-null ``replay`` means the
        request was already completed and should return the stored resource;
        a non-null ``record`` is the reservation this request must complete.
        """
        digest = request_digest(payload)
        if not key:
            return None, None, digest

        existing = self._get(user_id=user_id, operation=operation, key=key)
        if existing is not None:
            self._check(existing, digest)
            return existing, None, digest

        record = IdempotencyKey(
            user_id=user_id,
            operation=operation,
            key=key,
            request_hash=digest,
            status="pending",
            expires_at=datetime.now(UTC) + TTL,
        )
        try:
            with self.db.begin_nested():
                self.db.add(record)
                self.db.flush()
        except IntegrityError:
            # Another transaction won the race; its result is authoritative.
            existing = self._get(user_id=user_id, operation=operation, key=key)
            if existing is None:
                raise
            self._check(existing, digest)
            return existing, None, digest
        return None, record, digest

    @staticmethod
    def _check(record: IdempotencyKey, digest: str) -> None:
        if record.request_hash != digest:
            raise IdempotencyConflictError
        if record.status != "completed":
            raise IdempotencyInProgressError

    def complete(
        self,
        record: IdempotencyKey | None,
        *,
        resource_id: uuid.UUID,
        response: dict[str, Any] | None = None,
    ) -> None:
        if record is None:
            return
        record.status = "completed"
        record.resource_id = resource_id
        record.response = response
        self.db.flush()

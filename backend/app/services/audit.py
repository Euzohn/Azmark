import uuid
from ipaddress import ip_address
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_ip
from app.models.audit_log import AuditLog


def _is_trusted_proxy(host: str | None) -> bool:
    """True when ``host`` (request.client.host) is a configured reverse proxy.

    Only a trusted proxy's X-Forwarded-For may be used as the client address —
    a direct client can forge that header, so an untrusted peer's header is
    ignored and the peer address itself is used instead (spec #47, #96).
    """
    if not host:
        return False
    try:
        addr = ip_address(host)
    except ValueError:
        # Non-IP peers (unix sockets, the test client's "testclient", etc.)
        # are never trusted proxies.
        return False
    return any(addr in net for net in settings.trusted_proxy_networks)


def _forwarded_ip(value: str | None) -> str | None:
    """Real client address from ``X-Forwarded-For``, or None if unusable.

    Walks the chain from the right and returns the first hop that is not itself
    a trusted proxy. That is the address our own proxy actually saw, so a forged
    prefix is ignored even if the proxy appends (``$proxy_add_x_forwarded_for``)
    instead of overwriting the header.

    Values are parsed as IP addresses: a malformed entry makes the whole header
    untrusted (None) rather than storing arbitrary text in a ``String(64)``
    column — PostgreSQL would reject the insert and fail the request.
    """
    if not value:
        return None
    for raw in reversed(value.split(",")):
        hop = raw.strip()
        if not hop:
            continue
        try:
            addr = ip_address(hop)
        except ValueError:
            return None
        if not _is_trusted_proxy(str(addr)):
            return str(addr)
    return None


def client_ip(request: Request) -> str | None:
    client_host = request.client.host if request.client else None
    if client_host is None:
        return None
    if _is_trusted_proxy(client_host):
        forwarded = _forwarded_ip(request.headers.get("x-forwarded-for"))
        if forwarded:
            return forwarded
    return client_host


def client_user_agent(request: Request) -> str | None:
    """Sanitised client hint for tracing (spec #47, #96).

    Strips control characters (blocks header/log injection) and truncates, so a
    hostile client cannot smuggle newlines into stored audit rows. Not a secret,
    but never trusted verbatim.
    """
    raw = request.headers.get("user-agent")
    if not raw:
        return None
    cleaned = "".join(ch for ch in raw.strip() if ch.isprintable())
    return cleaned[:200] or None


def request_id(request: Request) -> str | None:
    """Opaque correlation id stamped on the request by ``RequestContextMiddleware``."""
    return getattr(request.state, "request_id", None)


class AuditService:
    """Records important actions (spec #47). Never log sensitive raw values (#45, #96)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        meta: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        if request is None:
            ip = None
        else:
            ip = client_ip(request)
        entry = AuditLog(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            meta=self._with_actor(meta, request),
            ip=ip,
            ip_hash=hash_ip(ip),
            user_agent=client_user_agent(request) if request is not None else None,
            request_id=request_id(request) if request is not None else None,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    @staticmethod
    def _with_actor(meta: dict[str, Any] | None, request: Request | None) -> dict[str, Any] | None:
        """Attribute the action to the access token that performed it (#85).

        JWT sessions leave ``request.state.actor`` unset, so existing call sites
        keep their metadata untouched.
        """
        if request is None:
            return meta
        actor = getattr(request.state, "actor", None)
        if not actor:
            return meta
        return {**(meta or {}), "actor": actor}

    def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        request_id: str | None = None,
        ip: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Cross-user audit trail for admins (spec #5, #47)."""
        conditions = []
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)
        if request_id:
            conditions.append(AuditLog.request_id == request_id)
        if ip:
            conditions.append(AuditLog.ip == ip)

        count_stmt = select(func.count()).select_from(AuditLog)
        stmt = select(AuditLog)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            stmt = stmt.where(condition)

        total = self.db.scalar(count_stmt)
        stmt = (
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

    def list_for_user(
        self, *, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> tuple[list[AuditLog], int]:
        total = self.db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id)
        )
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(total or 0)

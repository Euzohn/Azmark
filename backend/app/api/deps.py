import uuid
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import access_token_limiter
from app.core.security import PAT_PREFIX, decode_access_token
from app.models.personal_access_token import TokenScope
from app.models.user import User, UserRole, UserStatus
from app.services.access_token import AccessTokenService
from app.services.storage import StorageProvider

bearer_scheme = HTTPBearer(auto_error=False)

# Only mutating HTTP methods need the write scope; everything a read-only token
# can reach must stay side-effect free (spec #33, #85).
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    raw = credentials.credentials

    # Personal access token (spec #85): agents and scripts present a long-lived
    # secret instead of a browser session token.
    if raw.startswith(PAT_PREFIX):
        resolved = AccessTokenService(db).authenticate(raw)
        if resolved is None:
            raise unauthorized
        user, token = resolved

        if settings.pat_rate_limit_per_minute > 0 and not access_token_limiter.allow(str(token.id)):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": "60"},
            )

        if request.method not in SAFE_METHODS and token.scope != TokenScope.WRITE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This access token is read-only",
            )

        # Audit entries pick this up so the user can see which agent acted.
        request.state.auth_kind = "access_token"
        request.state.actor = {
            "kind": "access_token",
            "id": str(token.id),
            "name": token.name,
        }
        return user

    subject = decode_access_token(raw)
    if subject is None:
        raise unauthorized

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    request.state.auth_kind = "session"
    return user


def get_current_session_user(
    request: Request, current_user: User = Depends(get_current_user)
) -> User:
    """A human in the web UI — personal access tokens are refused (spec #69, #85).

    Approving an agent's proposal is the one action an agent must never be able
    to perform for itself, otherwise confirmation is theatre. Keeping this check
    in one dependency makes the rule impossible to forget on a new route.
    """
    if getattr(request.state, "auth_kind", None) != "session":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a signed-in browser session, not an access token",
        )
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin-only dependency (spec #5). Non-admins get 403, never data."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_flight_service(db: Session = Depends(get_db)):
    from app.services.transport import FlightService

    return FlightService(db)


def get_train_service(db: Session = Depends(get_db)):
    from app.services.transport import TrainService

    return TrainService(db)


def get_transport_service(db: Session = Depends(get_db)):
    from app.services.transport import OtherTransportService

    return OtherTransportService(db)


def get_hotel_service(db: Session = Depends(get_db)):
    from app.services.hotel import HotelService

    return HotelService(db)


def get_expense_service(db: Session = Depends(get_db)):
    from app.services.expense import ExpenseService

    return ExpenseService(db)


def get_note_service(db: Session = Depends(get_db)):
    from app.services.note import NoteService

    return NoteService(db)


def get_auth_service(db: Session = Depends(get_db)):
    from app.services.auth import AuthService

    return AuthService(db)


def get_audit_service(db: Session = Depends(get_db)):
    from app.services.audit import AuditService

    return AuditService(db)


def get_provider_keys_service(db: Session = Depends(get_db)):
    from app.services.provider_keys import ProviderKeyStore

    return ProviderKeyStore(db)


def get_ai_settings_service(db: Session = Depends(get_db)):
    from app.services.ai_settings import AiSettingsService

    return AiSettingsService(db)


def get_flight_enrichment_service(db: Session = Depends(get_db)):
    from app.services.flight_enrichment import FlightEnrichmentService

    return FlightEnrichmentService(db)


def get_trip_service(db: Session = Depends(get_db)):
    from app.services.trip import TripService

    return TripService(db)


def get_dashboard_service(db: Session = Depends(get_db)):
    from app.services.dashboard import DashboardService

    return DashboardService(db)


def get_ai_agent_service(db: Session = Depends(get_db)):
    from app.services.ai_agent import AiAgentService

    return AiAgentService(db)


def get_data_transfer_service(db: Session = Depends(get_db)):
    from app.services.data_transfer import DataTransferService

    return DataTransferService(db)


def get_data_source_service(db: Session = Depends(get_db)):
    from app.services.data_source import DataSourceService

    return DataSourceService(db)


def get_access_token_service(db: Session = Depends(get_db)):
    from app.services.access_token import AccessTokenService

    return AccessTokenService(db)


def get_admin_service(db: Session = Depends(get_db)):
    from app.services.admin import AdminService

    return AdminService(db)


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    """One S3 client per process (spec #44/#66)."""
    from app.services.storage import build_storage_provider

    return build_storage_provider()


def get_attachment_service(
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
):
    from app.services.attachment import AttachmentService

    return AttachmentService(db, storage)


def get_record_service(db: Session = Depends(get_db)):
    from app.services.record import RecordService

    return RecordService(db)


def get_pending_action_service(db: Session = Depends(get_db)):
    from app.services.pending_action import PendingActionService

    return PendingActionService(db)

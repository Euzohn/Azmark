import uuid
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole, UserStatus
from app.services.storage import StorageProvider

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
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

    subject = decode_access_token(credentials.credentials)
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
    return user


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

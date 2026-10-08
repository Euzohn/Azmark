import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User

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
    return user


def get_flight_service(db: Session = Depends(get_db)):
    from app.services.transport import FlightService

    return FlightService(db)


def get_auth_service(db: Session = Depends(get_db)):
    from app.services.auth import AuthService

    return AuthService(db)


def get_audit_service(db: Session = Depends(get_db)):
    from app.services.audit import AuditService

    return AuditService(db)


def get_provider_keys_service(db: Session = Depends(get_db)):
    from app.services.provider_keys import ProviderKeyStore

    return ProviderKeyStore(db)


def get_flight_enrichment_service(db: Session = Depends(get_db)):
    from app.services.flight_enrichment import FlightEnrichmentService

    return FlightEnrichmentService(db)

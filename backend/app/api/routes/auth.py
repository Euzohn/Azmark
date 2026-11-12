from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import (
    get_attachment_service,
    get_audit_service,
    get_auth_service,
    get_current_user,
    get_system_settings_service,
)
from app.core.captcha import (
    CAPTCHA_PROVIDER_TURNSTILE,
    create_captcha,
    verify_captcha,
    verify_turnstile,
)
from app.core.config import settings
from app.core.rate_limit import login_limiter, register_limiter
from app.core.security import create_access_token
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.auth import (
    AuthConfig,
    CaptchaChallenge,
    DeleteAccountRequest,
    LoginRequest,
    PasswordChange,
    RegisterRequest,
    TokenResponse,
    UsernameChange,
    UserRead,
    UserUpdate,
)
from app.services.attachment import AttachmentService
from app.services.audit import AuditService, client_ip
from app.services.auth import (
    AuthService,
    EmailTakenError,
    InvalidCredentialsError,
    LastAdminError,
    UsernameTakenError,
)
from app.services.system_setting import SystemSettingsService, effective_registration_captcha

router = APIRouter(prefix="/auth", tags=["auth"])


def _enforce_rate_limit(limiter, budget: int, request: Request, bucket: str, detail: str) -> None:
    """Reject the request with 429 once the per-IP budget is exhausted (spec #70)."""
    if budget <= 0:
        return
    key = f"{bucket}:{client_ip(request) or 'unknown'}"
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": "60"},
        )


@router.get("/config", response_model=AuthConfig)
def auth_config(
    service: SystemSettingsService = Depends(get_system_settings_service),
) -> AuthConfig:
    """Public registration posture so the anonymous forms can render correctly.

    The provider reported here is the *effective* one: Turnstile only when it
    is fully configured, otherwise arithmetic — exactly what the register
    endpoint enforces, so the form and the API never disagree.
    """
    row = service.get_or_create()
    provider, site_key, _secret = effective_registration_captcha(row)
    return AuthConfig(
        allow_registration=row.allow_registration,
        registration_captcha_enabled=row.registration_captcha_enabled,
        captcha_provider=provider,
        turnstile_site_key=site_key,
    )


@router.get("/captcha", response_model=CaptchaChallenge)
def captcha() -> CaptchaChallenge:
    token, question = create_captcha()
    return CaptchaChallenge(token=token, question=question)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    sys_settings: SystemSettingsService = Depends(get_system_settings_service),
    audit: AuditService = Depends(get_audit_service),
) -> User:
    row = sys_settings.get_or_create()
    if not row.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled on this instance",
        )
    # Count every attempt per client IP before any work is done; this also caps
    # captcha-token guess rate for the arithmetic challenge, whose token allows
    # answer retries (spec #70).
    _enforce_rate_limit(
        register_limiter,
        settings.register_rate_limit_per_minute,
        request,
        "register",
        "Too many registration attempts, please try again later",
    )
    if row.registration_captcha_enabled:
        provider, _site_key, turnstile_secret = effective_registration_captcha(row)
        if provider == CAPTCHA_PROVIDER_TURNSTILE:
            # Cloudflare Turnstile: the client sends the widget token as captcha_token.
            if not payload.captcha_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Captcha required"
                )
            if not verify_turnstile(payload.captcha_token, turnstile_secret, client_ip(request)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid captcha"
                )
        else:
            # Self-hosted arithmetic; also the fallback while Turnstile is
            # selected but not fully configured (site key or secret missing).
            if not payload.captcha_token or not payload.captcha_answer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Captcha required"
                )
            if not verify_captcha(payload.captcha_token, payload.captcha_answer):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid captcha"
                )
    try:
        user = service.register(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            display_name=payload.display_name,
        )
    except UsernameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        ) from None
    except EmailTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already in use"
        ) from None
    audit.log(action=AuditAction.REGISTER, user_id=user.id, request=request)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    audit: AuditService = Depends(get_audit_service),
):
    # Brute-force budget per client IP; every attempt counts so password
    # spraying across usernames and targeted guessing share one window (#70).
    _enforce_rate_limit(
        login_limiter,
        settings.login_rate_limit_per_minute,
        request,
        "login",
        "Too many login attempts, please try again later",
    )
    try:
        user = service.authenticate(username=payload.username, password=payload.password)
    except InvalidCredentialsError:
        audit.log(action=AuditAction.LOGIN_FAILED, request=request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        ) from None
    audit.log(action=AuditAction.LOGIN, user_id=user.id, request=request)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Tokens are stateless; clients drop them after this call (spec #4.3, #47)."""
    audit.log(action=AuditAction.LOGOUT, user_id=current_user.id, request=request)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    audit: AuditService = Depends(get_audit_service),
) -> User:
    fields = sorted(payload.model_dump(exclude_unset=True).keys())
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    user = service.users.save(current_user)
    audit.log(
        action=AuditAction.ACCOUNT_CHANGE,
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        meta={"fields": fields},
        request=request,
    )
    return user


@router.post("/me/password", response_model=UserRead)
def change_password(
    payload: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    audit: AuditService = Depends(get_audit_service),
) -> User:
    try:
        user = service.change_password(
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password"
        ) from None
    audit.log(action=AuditAction.PASSWORD_CHANGE, user_id=user.id, request=request)
    return user


@router.post("/me/username", response_model=UserRead)
def change_username(
    payload: UsernameChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    audit: AuditService = Depends(get_audit_service),
) -> User:
    try:
        user = service.change_username(
            user=current_user,
            current_password=payload.current_password,
            new_username=payload.new_username,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password"
        ) from None
    except UsernameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        ) from None
    audit.log(action=AuditAction.USERNAME_CHANGE, user_id=user.id, request=request)
    return user


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    attachments: AttachmentService = Depends(get_attachment_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Delete the account and owned data, keeping an anonymised audit trail (#48)."""
    user_id = current_user.id
    username = current_user.username
    try:
        service.delete_account(
            user=current_user,
            password=payload.password,
            attachments=attachments,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password"
        ) from None
    except LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last active admin",
        ) from None

    audit.log(
        action=AuditAction.ACCOUNT_DELETE,
        user_id=None,
        resource_type="user",
        resource_id=str(user_id),
        meta={"username": username},
        request=request,
    )

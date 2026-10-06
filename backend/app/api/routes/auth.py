from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_audit_service, get_auth_service, get_current_user
from app.core.security import create_access_token
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    RegisterRequest,
    TokenResponse,
    UsernameChange,
    UserRead,
    UserUpdate,
)
from app.services.audit import AuditService
from app.services.auth import AuthService, InvalidCredentialsError, UsernameTakenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    audit: AuditService = Depends(get_audit_service),
) -> User:
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
    audit.log(action=AuditAction.REGISTER, user_id=user.id, request=request)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        user = service.authenticate(username=payload.username, password=payload.password)
    except InvalidCredentialsError:
        audit.log(action=AuditAction.LOGIN_FAILED, request=request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        ) from None
    audit.log(action=AuditAction.LOGIN, user_id=user.id, request=request)
    return TokenResponse(access_token=create_access_token(str(user.id)))


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

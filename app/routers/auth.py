from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.auth import (
    AdminLoginRequest,
    OTPSentResponse,
    RefreshRequest,
    SendOTPRequest,
    TokenResponse,
    VerifyOTPRequest,
)
from app.schemas.common import ApiResponse
from app.schemas.user import UserRead, UserUpdate
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp", response_model=ApiResponse[OTPSentResponse])
@handle_exceptions
async def send_otp(
    body: SendOTPRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).send_otp(body.phone)
    return ApiResponse(
        message="Code envoyé par SMS",
        data=OTPSentResponse(phone=body.phone),
    )


@router.post("/verify-otp", response_model=ApiResponse[TokenResponse])
@handle_exceptions
async def verify_otp(
    body: VerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    name = request.headers.get("X-User-Name")
    service = AuthService(db)
    user, is_new = await service.login_with_otp(body.phone, body.code, name=name)
    tokens = service.issue_tokens(user)
    await service.persist_refresh_token(user.id, tokens["refresh_token"])
    return ApiResponse(
        message="Connexion réussie",
        data=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            is_new_user=is_new,
            user=AuthService.to_read(user),
        ),
    )


@router.post("/admin/login", response_model=ApiResponse[TokenResponse])
@handle_exceptions
async def admin_login(
    body: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    user = await service.admin_login(body)
    tokens = service.issue_tokens(user)
    await service.persist_refresh_token(user.id, tokens["refresh_token"])
    return ApiResponse(
        message="Connexion admin réussie",
        data=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=AuthService.to_read(user),
        ),
    )


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
@handle_exceptions
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    user, access, refresh = await service.refresh(body.refresh_token)
    return ApiResponse(
        message="Tokens renouvelés",
        data=TokenResponse(
            access_token=access,
            refresh_token=refresh,
            user=AuthService.to_read(user),
        ),
    )


@router.post("/logout", response_model=ApiResponse)
@handle_exceptions
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).logout(body.refresh_token)
    return ApiResponse(message="Déconnexion réussie")


@router.get("/me", response_model=ApiResponse[UserRead])
@handle_exceptions
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await AuthService(db).get_user(current_user.id)
    return ApiResponse(data=AuthService.to_read(user))


@router.patch("/me", response_model=ApiResponse[UserRead])
@handle_exceptions
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await AuthService(db).update_profile(
        current_user, body.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=AuthService.to_read(user))

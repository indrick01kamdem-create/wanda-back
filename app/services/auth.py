from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import AdminLoginRequest
from app.schemas.user import UserRead
from app.services.otp import OTPService
from app.services.wallet import WalletService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── OTP flow ───────────────────────────────────────────────────────────────

    async def send_otp(self, phone: str) -> None:
        await OTPService(self._db).send_otp(phone)

    async def login_with_otp(self, phone: str, code: str, name: str | None = None) -> tuple[User, bool]:
        """Vérifie l'OTP, crée le compte si absent, retourne (user, is_new)."""
        await OTPService(self._db).verify_otp(phone, code)

        result = await self._db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()

        is_new = False
        if user is None:
            user = User(
                phone=phone,
                is_phone_verified=True,
                name=name or _default_name(phone),
            )
            self._db.add(user)
            await self._db.flush()
            await WalletService(self._db).get_or_create(user.id)
            is_new = True
        elif not user.is_phone_verified:
            user.is_phone_verified = True

        await self._db.commit()
        await self._db.refresh(user)
        return user, is_new

    async def admin_login(self, data: AdminLoginRequest) -> User:
        result = await self._db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()
        if user is None or not user.is_admin:
            raise UnauthorizedException("Email ou mot de passe incorrect")
        if not user.hashed_password or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException("Email ou mot de passe incorrect")
        if not user.is_active:
            raise UnauthorizedException("Compte désactivé")
        return user

    # ── Tokens ─────────────────────────────────────────────────────────────────

    def issue_tokens(self, user: User) -> dict[str, str]:
        access = create_access_token(
            subject=user.id,
            extra={"role": user.role, "is_admin": user.is_admin},
            expires_minutes=settings.access_token_expire_minutes,
        )
        refresh = create_refresh_token(
            subject=user.id, expires_minutes=settings.refresh_token_expire_minutes
        )
        return {"access_token": access, "refresh_token": refresh}

    async def persist_refresh_token(self, user_id: str, token: str) -> None:
        self._db.add(
            RefreshToken(
                user_id=user_id,
                token=token,
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=settings.refresh_token_expire_minutes),
            )
        )
        await self._db.commit()

    async def refresh(self, refresh_token: str) -> tuple[User, str, str]:
        """Valide un refresh token et émet un nouveau couple de tokens."""
        result = await self._db.execute(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token, RefreshToken.is_revoked.is_(False)
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise UnauthorizedException("Refresh token invalide")

        if record.expires_at.tzinfo is None:
            record.expires_at = record.expires_at.replace(tzinfo=timezone.utc)
        if record.expires_at < datetime.now(timezone.utc):
            record.is_revoked = True
            await self._db.commit()
            raise UnauthorizedException("Session expirée, reconnectez-vous")

        user = await self._db.get(User, record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException("Compte introuvable ou désactivé")

        tokens = self.issue_tokens(user)
        return user, tokens["access_token"], tokens["refresh_token"]

    async def logout(self, refresh_token: str) -> None:
        result = await self._db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        record = result.scalar_one_or_none()
        if record is not None:
            record.is_revoked = True
            await self._db.commit()

    # ── Profile helpers ────────────────────────────────────────────────────────

    async def get_user(self, user_id: str) -> User:
        user = await self._db.get(User, user_id)
        if user is None:
            raise NotFoundException("Utilisateur introuvable")
        return user

    async def update_profile(self, user: User, data: dict) -> User:
        for key, value in data.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    @staticmethod
    def to_read(user: User) -> UserRead:
        return UserRead.model_validate(user)


def _default_name(phone: str) -> str:
    return f"Passager {phone[-4:]}"

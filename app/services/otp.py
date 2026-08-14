from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.models.otp import PhoneOTP
from app.services.sms.factory import get_sms_provider

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT_SECONDS = 60


class OTPService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def send_otp(self, phone: str) -> None:
        await self._check_rate_limit(phone)
        await self._invalidate_existing(phone)

        code = _generate_code()
        otp = PhoneOTP(
            phone=phone,
            code_hash=_hash_code(code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
        )
        self._db.add(otp)
        await self._db.commit()

        provider = get_sms_provider()
        await provider.send(phone, code)
        logger.info("OTP envoyé à %s", _mask(phone))

    async def verify_otp(self, phone: str, code: str) -> None:
        otp = await self._get_active_otp(phone)
        if otp is None:
            raise UnauthorizedException("Aucun code en attente pour ce numéro")

        expires = otp.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            otp.is_used = True
            await self._db.commit()
            raise UnauthorizedException("Le code a expiré. Demandez-en un nouveau.")

        if otp.attempt_count >= OTP_MAX_ATTEMPTS:
            otp.is_used = True
            await self._db.commit()
            raise UnauthorizedException("Trop de tentatives. Demandez un nouveau code.")

        provider = get_sms_provider()
        approved = await provider.verify(phone, code, otp.code_hash)

        if not approved:
            otp.attempt_count += 1
            remaining = OTP_MAX_ATTEMPTS - otp.attempt_count
            await self._db.commit()
            raise UnauthorizedException(f"Code incorrect. {remaining} tentative(s) restante(s).")

        otp.is_used = True
        await self._db.commit()
        logger.info("OTP vérifié pour %s", _mask(phone))

    async def _check_rate_limit(self, phone: str) -> None:
        since = datetime.now(timezone.utc) - timedelta(seconds=OTP_RATE_LIMIT_SECONDS)
        result = await self._db.execute(
            select(PhoneOTP)
            .where(PhoneOTP.phone == phone, PhoneOTP.created_at >= since)
            .limit(1)
        )
        if result.scalar_one_or_none():
            raise BadRequestException(
                f"Un code a déjà été envoyé. Attendez {OTP_RATE_LIMIT_SECONDS} secondes."
            )

    async def _invalidate_existing(self, phone: str) -> None:
        await self._db.execute(
            update(PhoneOTP)
            .where(PhoneOTP.phone == phone, PhoneOTP.is_used.is_(False))
            .values(is_used=True)
        )

    async def _get_active_otp(self, phone: str) -> PhoneOTP | None:
        result = await self._db.execute(
            select(PhoneOTP)
            .where(PhoneOTP.phone == phone, PhoneOTP.is_used.is_(False))
            .order_by(PhoneOTP.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _generate_code() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(OTP_LENGTH))


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _mask(phone: str) -> str:
    if len(phone) <= 6:
        return "****"
    return phone[:4] + "****" + phone[-3:]

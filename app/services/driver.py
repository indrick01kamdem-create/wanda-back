from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.driver import (
    APPROVAL_APPROVED,
    DRIVER_STATUS_OFFLINE,
    KYC_REJECTED,
    DriverProfile,
)
from app.models.user import USER_ROLE_DRIVER, User
from app.schemas.driver import (
    DriverApprovalUpdate,
    DriverEditRequest,
    DriverKYCUpdate,
    DriverLocationUpdate,
)

logger = logging.getLogger(__name__)


class DriverService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create(self, user: User) -> DriverProfile:
        result = await self._db.execute(
            select(DriverProfile).where(DriverProfile.user_id == user.id)
        )
        profile = result.scalar_one_or_none()
        if profile is not None:
            return profile

        user.role = USER_ROLE_DRIVER
        profile = DriverProfile(user_id=user.id)
        self._db.add(profile)
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    async def get_by_user_id(self, user_id: str) -> DriverProfile:
        result = await self._db.execute(
            select(DriverProfile).where(DriverProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise NotFoundException("Profil chauffeur introuvable")
        return profile

    async def get_by_user_id_with_user(self, user_id: str) -> DriverProfile:
        result = await self._db.execute(
            select(DriverProfile)
            .options(selectinload(DriverProfile.user))
            .where(DriverProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise NotFoundException("Profil chauffeur introuvable")
        return profile

    async def get_by_id(self, profile_id: str) -> DriverProfile:
        profile = await self._db.get(DriverProfile, profile_id)
        if profile is None:
            raise NotFoundException("Profil chauffeur introuvable")
        return profile

    async def update_location(self, user_id: str, data: DriverLocationUpdate) -> DriverProfile:
        profile = await self.get_by_user_id(user_id)
        if data.lat is not None:
            profile.lat = data.lat
        if data.lng is not None:
            profile.lng = data.lng
        if data.is_online is not None:
            profile.is_online = data.is_online
            if data.is_online:
                profile.status = "idle"
            else:
                profile.status = DRIVER_STATUS_OFFLINE
        if data.status is not None:
            profile.status = data.status
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    async def edit_profile(self, profile: DriverProfile, data: DriverEditRequest) -> DriverProfile:
        for key in ("vehicle_type", "vehicle_model", "vehicle_color", "vehicle_plate",
                    "cnic_number", "license_number", "forensic_notes"):
            value = getattr(data, key)
            if value is not None:
                setattr(profile, key, value)
        if data.kyc_documents is not None:
            profile.kyc_documents = {
                k: v.model_dump() for k, v in data.kyc_documents.items()
            }
        if data.name is not None or data.phone is not None:
            user = await self._db.get(User, profile.user_id)
            if user is not None:
                if data.name is not None:
                    user.name = data.name
                if data.phone is not None:
                    user.phone = data.phone
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    # ── Admin flows ────────────────────────────────────────────────────────────

    async def approve(self, user_id: str, data: DriverApprovalUpdate) -> DriverProfile:
        profile = await self.get_by_user_id(user_id)
        profile.approval_status = data.approval_status
        profile.rejection_reason = data.rejection_reason
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    async def update_kyc(self, user_id: str, data: DriverKYCUpdate) -> DriverProfile:
        profile = await self.get_by_user_id(user_id)
        profile.kyc_status = data.kyc_status
        if data.kyc_documents is not None:
            profile.kyc_documents = {
                k: v.model_dump() for k, v in data.kyc_documents.items()
            }
        if data.kyc_status == KYC_REJECTED:
            profile.approval_status = "pending"
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    async def list_drivers(
        self, *, approval_status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[DriverProfile], int]:
        count_stmt = select(DriverProfile.id)
        stmt = select(DriverProfile).options(selectinload(DriverProfile.user))
        if approval_status:
            count_stmt = count_stmt.where(DriverProfile.approval_status == approval_status)
            stmt = stmt.where(DriverProfile.approval_status == approval_status)

        total = len((await self._db.execute(count_stmt)).scalars().all())
        stmt = stmt.order_by(DriverProfile.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._db.execute(stmt)).scalars().all()
        return list(rows), total

    # ── Carte publique ─────────────────────────────────────────────────────────

    async def list_online(self, limit: int = 100) -> list[DriverProfile]:
        """Chauffeurs approuvés, en ligne, avec position — pour la carte passager."""
        stmt = (
            select(DriverProfile)
            .where(
                DriverProfile.is_online.is_(True),
                DriverProfile.approval_status == APPROVAL_APPROVED,
                DriverProfile.lat.is_not(None),
                DriverProfile.lng.is_not(None),
            )
            .options(selectinload(DriverProfile.user))
            .order_by(DriverProfile.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return list(rows)

    # ── Dispatch ───────────────────────────────────────────────────────────────

    async def find_nearby_driver(
        self, lat: float, lng: float, ride_class_id: str, radius_km: float = 5.0
    ) -> DriverProfile | None:
        """Recherche un chauffeur en ligne, approuvé, compatible avec la classe."""
        from math import asin, cos, pi, sin, sqrt

        rows = (
            await self._db.execute(
                select(DriverProfile).where(
                    DriverProfile.is_online.is_(True),
                    DriverProfile.approval_status == APPROVAL_APPROVED,
                    DriverProfile.lat.is_not(None),
                    DriverProfile.lng.is_not(None),
                )
            )
        ).scalars().all()

        def haversine(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
            r = 6371.0
            p = pi / 180
            dlat = (b_lat - a_lat) * p
            dlng = (b_lng - a_lng) * p
            h = sin(dlat / 2) ** 2 + cos(a_lat * p) * cos(b_lat * p) * sin(dlng / 2) ** 2
            return 2 * r * asin(sqrt(h))

        best: DriverProfile | None = None
        best_dist = radius_km
        for profile in rows:
            dist = haversine(lat, lng, profile.lat or 0, profile.lng or 0)
            if dist <= best_dist:
                best = profile
                best_dist = dist
        return best

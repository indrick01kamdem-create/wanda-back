from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import hash_password
from app.models.admin import AdminAccount
from app.models.driver import APPROVAL_PENDING, APPROVAL_APPROVED, DriverProfile
from app.models.ride import (
    RIDE_STATUS_CANCELLED,
    RIDE_STATUS_COMPLETED,
    RIDE_STATUS_SEARCHING,
    Ride,
)
from app.models.transaction import WalletTransaction
from app.models.user import USER_ROLE_DRIVER, USER_ROLE_PASSENGER, User
from app.schemas.admin import AdminCreate, AdminUpdate

logger = logging.getLogger(__name__)


class AdminService:
    """Tableau de bord admin (KPI) et gestion du roster."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def kpi(self) -> dict:
        total_users = (
            await self._db.execute(select(func.count(User.id)))
        ).scalar_one()
        total_drivers = (
            await self._db.execute(
                select(func.count(DriverProfile.id)).where(
                    DriverProfile.approval_status == APPROVAL_APPROVED
                )
            )
        ).scalar_one()
        pending_drivers = (
            await self._db.execute(
                select(func.count(DriverProfile.id)).where(
                    DriverProfile.approval_status == APPROVAL_PENDING
                )
            )
        ).scalar_one()

        total_rides = (
            await self._db.execute(select(func.count(Ride.id)))
        ).scalar_one()
        completed = (
            await self._db.execute(
                select(func.count(Ride.id)).where(Ride.status == RIDE_STATUS_COMPLETED)
            )
        ).scalar_one()
        cancelled = (
            await self._db.execute(
                select(func.count(Ride.id)).where(Ride.status == RIDE_STATUS_CANCELLED)
            )
        ).scalar_one()

        total_fare = (
            await self._db.execute(
                select(func.coalesce(func.sum(Ride.fare), 0)).where(
                    Ride.status == RIDE_STATUS_COMPLETED
                )
            )
        ).scalar_one()
        total_commission = (
            await self._db.execute(
                select(func.coalesce(func.sum(Ride.platform_commission), 0)).where(
                    Ride.status == RIDE_STATUS_COMPLETED
                )
            )
        ).scalar_one()

        pending_withdrawals = (
            await self._db.execute(
                select(func.count(WalletTransaction.id)).where(
                    WalletTransaction.type == "withdrawal",
                    WalletTransaction.status == "pending",
                )
            )
        ).scalar_one()

        return {
            "total_users": total_users,
            "total_drivers": total_drivers,
            "total_rides": total_rides,
            "completed_rides": completed,
            "cancelled_rides": cancelled,
            "total_revenue_fcfa": total_fare,
            "total_commission_fcfa": total_commission,
            "pending_withdrawals": pending_withdrawals,
            "pending_driver_approvals": pending_drivers,
        }

    # ── Staff roster (AdminAccount) ─────────────────────────────────────────────

    async def list_staff(self) -> list[AdminAccount]:
        rows = (
            await self._db.execute(select(AdminAccount).order_by(AdminAccount.created_at))
        ).scalars().all()
        return list(rows)

    async def create_staff(self, data: AdminCreate, assigned_by: str | None = None) -> AdminAccount:
        existing = (
            await self._db.execute(select(User).where(User.email == data.email))
        ).scalar_one_or_none()
        if existing is not None:
            raise BadRequestException("Un compte existe déjà avec cet email")

        user = User(
            email=data.email,
            name=data.name or data.email.split("@")[0],
            hashed_password=hash_password(data.password),
            is_admin=True,
            admin_role=data.role,
            phone=f"admin_{uuid.uuid4().hex[:12]}",
        )
        self._db.add(user)
        await self._db.flush()

        admin = AdminAccount(
            user_id=user.id,
            email=data.email,
            name=user.name,
            role=data.role,
            department_name=data.department_name,
            assigned_by=assigned_by,
        )
        self._db.add(admin)
        await self._db.commit()
        await self._db.refresh(admin)
        return admin

    async def update_staff(self, admin_id: str, data: AdminUpdate) -> AdminAccount:
        admin = await self._db.get(AdminAccount, admin_id)
        if admin is None:
            raise NotFoundException("Compte admin introuvable")

        if data.name is not None:
            admin.name = data.name
        if data.role is not None:
            admin.role = data.role
        if data.department_name is not None:
            admin.department_name = data.department_name
        if data.active is not None:
            admin.active = data.active

        user = (
            await self._db.execute(select(User).where(User.id == admin.user_id))
        ).scalar_one_or_none()
        if user is not None:
            if data.name is not None:
                user.name = data.name
            if data.role is not None:
                user.admin_role = data.role
            if data.active is not None:
                user.is_active = data.active

        await self._db.commit()
        await self._db.refresh(admin)
        return admin

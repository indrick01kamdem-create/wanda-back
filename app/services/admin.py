from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.driver import APPROVAL_PENDING, APPROVAL_APPROVED, DriverProfile
from app.models.ride import (
    RIDE_STATUS_CANCELLED,
    RIDE_STATUS_COMPLETED,
    RIDE_STATUS_SEARCHING,
    Ride,
)
from app.models.transaction import WalletTransaction
from app.models.user import USER_ROLE_DRIVER, USER_ROLE_PASSENGER, User

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

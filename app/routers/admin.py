from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin, get_db, require_admin_role
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.admin import KpiSummary
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.driver import (
    DriverApprovalUpdate,
    DriverKYCUpdate,
    DriverProfileRead,
)
from app.schemas.settings import (
    NotificationCreate,
    NotificationRead,
    NotificationScheduleRead,
    NotificationScheduleUpdate,
    SystemSettingsRead,
    SystemSettingsUpdate,
)
from app.schemas.wallet import WalletTransactionRead
from app.services.admin import AdminService
from app.services.driver import DriverService
from app.services.notification import NotificationService
from app.services.settings import SettingsService
from app.services.transaction import WithdrawalService

router = APIRouter(prefix="/admin", tags=["admin"])

_super = require_admin_role(["super_admin"])
# Tout admin authentifié (super_admin, accounting, publicity, forensic) peut
# consulter ces routes. Le rôle "forensic" est volontairement lecture seule :
# il n'est jamais listé dans un require_admin_role(...) plus bas, donc il ne
# peut approuver/rejeter aucune action (drivers, retraits, settings,
# notifications) — seulement consulter (KPI, roster, historique).
_any_admin = get_current_admin


@router.get("/kpi", response_model=ApiResponse[KpiSummary])
@handle_exceptions
async def kpi(
    _admin: User = Depends(_any_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await AdminService(db).kpi()
    return ApiResponse(data=KpiSummary(**data))


# ── Drivers ───────────────────────────────────────────────────────────────────

@router.get("/drivers", response_model=ApiResponse[PaginatedResponse[DriverProfileRead]])
@handle_exceptions
async def list_drivers(
    approval_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(_any_admin),
    db: AsyncSession = Depends(get_db),
):
    drivers, total = await DriverService(db).list_drivers(
        approval_status=approval_status,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    items = []
    for d in drivers:
        item = DriverProfileRead.model_validate(d).model_dump()
        if d.user:
            item["user_name"] = d.user.name
            item["user_phone"] = d.user.phone
        items.append(DriverProfileRead(**item))
    return ApiResponse(
        data=PaginatedResponse.build(items, total, page, per_page)
    )


@router.post("/drivers/{user_id}/approval", response_model=ApiResponse[DriverProfileRead])
@handle_exceptions
async def approve_driver(
    user_id: str,
    body: DriverApprovalUpdate,
    _admin: User = Depends(_super),
    db: AsyncSession = Depends(get_db),
):
    profile = await DriverService(db).approve(user_id, body)
    return ApiResponse(data=DriverProfileRead.model_validate(profile))


@router.post("/drivers/{user_id}/kyc", response_model=ApiResponse[DriverProfileRead])
@handle_exceptions
async def update_driver_kyc(
    user_id: str,
    body: DriverKYCUpdate,
    _admin: User = Depends(_super),
    db: AsyncSession = Depends(get_db),
):
    profile = await DriverService(db).update_kyc(user_id, body)
    return ApiResponse(data=DriverProfileRead.model_validate(profile))


# ── Withdrawals ───────────────────────────────────────────────────────────────

@router.get("/withdrawals", response_model=ApiResponse[list[WalletTransactionRead]])
@handle_exceptions
async def list_withdrawals(
    _admin: User = Depends(require_admin_role(["super_admin", "accounting"])),
    db: AsyncSession = Depends(get_db),
):
    txs = await WithdrawalService(db).list_pending()
    return ApiResponse(data=[WalletTransactionRead.model_validate(t) for t in txs])


@router.post("/withdrawals/{tx_id}/approve", response_model=ApiResponse[WalletTransactionRead])
@handle_exceptions
async def approve_withdrawal(
    tx_id: str,
    _admin: User = Depends(require_admin_role(["super_admin", "accounting"])),
    db: AsyncSession = Depends(get_db),
):
    from app.services.payment.factory import PaymentFactory

    tx = await WithdrawalService(db).approve(tx_id, PaymentFactory.get_default())
    return ApiResponse(message="Retrait transféré", data=WalletTransactionRead.model_validate(tx))


@router.post("/withdrawals/{tx_id}/reject", response_model=ApiResponse[WalletTransactionRead])
@handle_exceptions
async def reject_withdrawal(
    tx_id: str,
    _admin: User = Depends(require_admin_role(["super_admin", "accounting"])),
    db: AsyncSession = Depends(get_db),
):
    tx = await WithdrawalService(db).reject(tx_id)
    return ApiResponse(message="Retrait rejeté", data=WalletTransactionRead.model_validate(tx))


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=ApiResponse[SystemSettingsRead])
@handle_exceptions
async def get_settings(
    _admin: User = Depends(_any_admin),
    db: AsyncSession = Depends(get_db),
):
    settings = await SettingsService(db).get()
    return ApiResponse(data=SystemSettingsRead.model_validate(settings))


@router.patch("/settings", response_model=ApiResponse[SystemSettingsRead])
@handle_exceptions
async def update_settings(
    body: SystemSettingsUpdate,
    _admin: User = Depends(_super),
    db: AsyncSession = Depends(get_db),
):
    settings = await SettingsService(db).update(body)
    return ApiResponse(data=SystemSettingsRead.model_validate(settings))


# ── Notifications ─────────────────────────────────────────────────────────────

@router.post("/notifications", response_model=ApiResponse[NotificationRead])
@handle_exceptions
async def broadcast(
    body: NotificationCreate,
    _admin: User = Depends(require_admin_role(["super_admin", "publicity"])),
    db: AsyncSession = Depends(get_db),
):
    notification = await NotificationService(db).create(body.model_dump())
    return ApiResponse(message="Notification diffusée", data=NotificationRead.model_validate(notification))


@router.get("/notifications", response_model=ApiResponse[list[NotificationRead]])
@handle_exceptions
async def list_notifications(
    _admin: User = Depends(_any_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.settings import Notification

    rows = (
        await db.execute(
            select(Notification).order_by(Notification.created_at.desc()).limit(100)
        )
    ).scalars().all()
    return ApiResponse(data=[NotificationRead.model_validate(n) for n in rows])


@router.get("/notification-schedule", response_model=ApiResponse[NotificationScheduleRead])
@handle_exceptions
async def get_schedule(
    _admin: User = Depends(_any_admin),
    db: AsyncSession = Depends(get_db),
):
    schedule = await SettingsService(db).get_schedule()
    return ApiResponse(data=NotificationScheduleRead.model_validate(schedule))


@router.patch("/notification-schedule", response_model=ApiResponse[NotificationScheduleRead])
@handle_exceptions
async def update_schedule(
    body: NotificationScheduleUpdate,
    _admin: User = Depends(require_admin_role(["super_admin", "publicity"])),
    db: AsyncSession = Depends(get_db),
):
    schedule = await SettingsService(db).update_schedule(body)
    return ApiResponse(data=NotificationScheduleRead.model_validate(schedule))

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.payment import PaymentDetailRead, PaymentRead, SyncInstallmentRequest
from app.schemas.wallet import WalletTopupRequest, WalletTopupResponse
from app.services.payment.factory import PaymentFactory
from app.services.payment.service import PaymentService
from app.services.settings import SettingsService

router = APIRouter(prefix="/payments", tags=["payments"])

# ── SSE waiter registry ────────────────────────────────────────────────────────
_payment_waiters: dict[str, asyncio.Queue] = {}


async def _notify_waiter(trans_id: str, status: str) -> None:
    waiter = _payment_waiters.get(trans_id)
    if waiter is not None and not waiter.full():
        await waiter.put({"paid": status == "paid", "status": status})


def _get_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db, PaymentFactory.get_default())


# ── Topup ──────────────────────────────────────────────────────────────────────

@router.post("/topup", response_model=ApiResponse[WalletTopupResponse])
@handle_exceptions
async def topup_wallet(
    body: WalletTopupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await PaymentService(
        db, PaymentFactory.get_provider(body.provider)
    ).create_topup(
        user_id=current_user.id,
        amount=body.amount,
        phone=body.phone,
        provider_name=body.provider,
        redirect_url=body.redirect_url,
    )

    settings = await SettingsService(db).get()
    bonus_rate = settings.topup_promo_rate if settings.topup_promo_active else 0
    expected_bonus = round(body.amount * bonus_rate / 100) if bonus_rate else 0

    first = payment.installments[0] if payment.installments else None
    return ApiResponse(
        message="Paiement initié",
        data=WalletTopupResponse(
            payment_id=payment.id,
            status=payment.status,
            payment_url=first.payment_url if first else None,
            ussd_code=None,
            transaction_id=first.provider_transaction_id if first else None,
            amount=payment.total_amount,
            bonus_rate=bonus_rate,
            expected_bonus=expected_bonus,
        ),
    )


# ── Poll / SSE ────────────────────────────────────────────────────────────────

@router.get("/poll/{trans_id}")
async def poll_payment_status(trans_id: str) -> dict:
    """Le client interroge toutes les ~3s pour vérifier la confirmation."""
    provider = PaymentFactory.get_default()
    try:
        status = await provider.verify(trans_id)
        return {"status": status.status, "paid": status.status == "paid"}
    except Exception:
        return {"status": "pending", "paid": False}


@router.get("/stream/{trans_id}", include_in_schema=False)
async def stream_payment_status(trans_id: str):
    """
    SSE — le client se connecte une fois et attend le webhook.
    Emet un événement JSON unique : {"paid": bool, "status": str}
    Timeout de secours après 90s.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    _payment_waiters[trans_id] = queue

    async def generator():
        try:
            for _ in range(6):
                try:
                    result = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(result)}\n\n"
                    return
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            yield f"data: {json.dumps({'status': 'timeout', 'paid': False})}\n\n"
        finally:
            _payment_waiters.pop(trans_id, None)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Read / sync / cancel ──────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse[list[PaymentRead]])
@handle_exceptions
async def list_payments(
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(_get_service),
):
    payments = await service.list_user_payments(current_user.id)
    return ApiResponse(data=[PaymentRead.model_validate(p) for p in payments])


@router.get("/{payment_id}", response_model=ApiResponse[PaymentDetailRead])
@handle_exceptions
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(_get_service),
):
    payment = await service.get_payment(payment_id, current_user.id)
    return ApiResponse(data=PaymentDetailRead.model_validate(payment))


@router.post("/installments/{installment_id}/sync", response_model=ApiResponse[PaymentRead])
@handle_exceptions
async def sync_installment(
    installment_id: str,
    body: SyncInstallmentRequest,
    service: PaymentService = Depends(_get_service),
):
    installment = await service.sync_installment_status(installment_id)
    return ApiResponse(data=PaymentRead.model_validate(installment.payment))


@router.delete("/{payment_id}", response_model=ApiResponse[PaymentRead])
@handle_exceptions
async def cancel_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(_get_service),
):
    payment = await service.cancel_payment(payment_id, current_user.id)
    return ApiResponse(data=PaymentRead.model_validate(payment))


# ── Webhook provider (Fapshi, etc.) ──────────────────────────────────────────

@router.post("/webhook/payment-status", include_in_schema=False)
async def provider_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Reçoit les notifications du provider (tableau de 1+ événements).
    Idempotent : chaque événement traité indépendamment.
    """
    import logging

    logger = logging.getLogger(__name__)

    body = await request.json()
    events = body if isinstance(body, list) else [body]

    provider = PaymentFactory.get_default()
    service = PaymentService(db, provider)

    for raw in events:
        try:
            event = provider.parse_webhook(raw)
            await service.handle_webhook(
                provider_transaction_id=event.transaction_id,
                raw_status=event.status,
                amount=event.amount,
            )
            if event.status in ("paid", "failed"):
                await _notify_waiter(event.transaction_id, event.status)
        except Exception as exc:
            logger.error("Webhook processing error for %s: %s", raw.get("transId"), exc)

    return {"received": True}

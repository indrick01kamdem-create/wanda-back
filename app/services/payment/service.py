"""
PaymentService — Orchestrateur des paiements Wanda (wallet topup, ride).

Architecture calquée sur cloudbaby :
  - Payment + PaymentInstallment (une tranche par paiement simple).
  - State pattern (app/services/payment/states.py) pour les transitions.
  - Provider injecté via IPaymentProvider (mock/fapshi).

Différence clé vs cloudbaby : pas de concept Order. Un Payment est lié à un
user + un payment_type ('wallet_topup' | 'ride_payment'). À la confirmation
complète, le service déclenche un hook (credit du wallet, etc.).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import Payment, PaymentInstallment
from app.services.payment.base import IPaymentProvider
from app.services.payment.states import resolve_state

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, db: AsyncSession, provider: IPaymentProvider) -> None:
        self._db = db
        self._provider = provider

    # ─────────────────────────────────────────────────────────────────────────
    # Create
    # ─────────────────────────────────────────────────────────────────────────

    async def create_topup(
        self,
        user_id: str,
        amount: int,
        phone: str,
        *,
        provider_name: str | None = None,
        redirect_url: str | None = None,
        external_id: str | None = None,
    ) -> Payment:
        """
        Crée un paiement de rechargement de wallet et initie la tranche
        auprès du provider (lien Fapshi / USSD mock).
        """
        if amount <= 0:
            raise HTTPException(400, "Le montant doit être positif")

        from app.services.payment.factory import PaymentFactory

        provider = PaymentFactory.get_provider(provider_name)

        payment = Payment(
            payment_type="wallet_topup",
            user_id=user_id,
            external_id=external_id,
            total_amount=amount,
            paid_amount=0,
            status="pending",
            provider=provider.provider_name,
            redirect_url=redirect_url,
        )
        self._db.add(payment)
        await self._db.flush()

        await self._create_installment(payment, amount, phone, user_id)

        # Dev : le provider mock est confirmé immédiatement (simule le webhook
        # provider). En prod (fapshi), le crédit attend la notification webhook.
        if self._provider.provider_name == "mock":
            await self._db.refresh(payment, ["installments"])
            inst = payment.installments[0] if payment.installments else None
            if inst is not None and inst.status == "pending" and inst.provider_transaction_id:
                status = await self._provider.verify(inst.provider_transaction_id)
                if status.status == "paid":
                    await self._confirm_installment(inst, payment, status.amount)

        await self._db.commit()
        await self._db.refresh(payment)
        return payment

    # ─────────────────────────────────────────────────────────────────────────
    # Webhook handler
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_webhook(
        self, provider_transaction_id: str, raw_status: str, amount: int | None
    ) -> None:
        """Traite un webhook provider. raw_status est normalisé ('paid'|'failed'|...)."""
        installment = await self._get_installment_by_provider_id(provider_transaction_id)
        if installment is None:
            logger.warning("Webhook: tranche inconnue transId=%s", provider_transaction_id)
            return

        payment = installment.payment

        if raw_status == "paid":
            await self._confirm_installment(installment, payment, amount)
        elif raw_status == "failed":
            await self._fail_installment(installment, payment, "Échec provider")

        await self._db.commit()

    async def sync_installment_status(self, installment_id: str) -> PaymentInstallment:
        """Poll du provider pour une tranche en attente (si webhook non reçu)."""
        result = await self._db.execute(
            select(PaymentInstallment)
            .options(
                selectinload(PaymentInstallment.payment).selectinload(Payment.installments)
            )
            .where(PaymentInstallment.id == installment_id)
        )
        installment = result.scalar_one_or_none()
        if installment is None:
            raise HTTPException(404, "Tranche introuvable")

        if installment.status != "pending" or not installment.provider_transaction_id:
            return installment

        status = await self._provider.verify(installment.provider_transaction_id)
        payment = installment.payment

        if status.status == "paid":
            await self._confirm_installment(installment, payment, status.amount)
        elif status.status == "failed":
            await self._fail_installment(installment, payment, "Échec provider")

        await self._db.commit()
        await self._db.refresh(installment)
        return installment

    # ─────────────────────────────────────────────────────────────────────────
    # Cancel / Read
    # ─────────────────────────────────────────────────────────────────────────

    async def cancel_payment(self, payment_id: str, user_id: str) -> Payment:
        payment = await self._get_payment(payment_id)
        if payment.user_id != user_id:
            raise HTTPException(403, "Non autorisé")

        state = resolve_state(payment.status)
        try:
            state.on_cancel(payment, "Annulé par l'utilisateur")
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        for inst in payment.installments:
            if inst.status == "pending":
                inst.status = "cancelled"

        await self._db.commit()
        await self._db.refresh(payment)
        return payment

    async def get_payment(self, payment_id: str, user_id: str) -> Payment:
        payment = await self._get_payment(payment_id)
        if payment.user_id != user_id:
            raise HTTPException(403, "Non autorisé")
        return payment

    async def list_user_payments(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[Payment]:
        result = await self._db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _create_installment(
        self,
        payment: Payment,
        amount: int,
        phone: str,
        user_id: str,
    ) -> PaymentInstallment:
        """Appelle le provider et persiste la tranche."""
        try:
            init = await self._provider.initiate(
                amount=amount,
                phone=phone,
                order_id=payment.id,
            )
        except Exception as exc:
            logger.error("Provider initiate error: %s", exc)
            raise HTTPException(502, f"Erreur provider paiement: {exc}")

        installment = PaymentInstallment(
            payment_id=payment.id,
            payer_user_id=user_id,
            payer_phone=phone,
            amount=amount,
            status="pending",
            provider=self._provider.provider_name,
            provider_transaction_id=init.transaction_id,
            payment_url=init.payment_url,
        )
        self._db.add(installment)
        return installment

    async def _confirm_installment(
        self,
        installment: PaymentInstallment,
        payment: Payment,
        amount: int | None,
    ) -> None:
        if installment.status == "paid":
            return  # idempotent

        confirmed_amount = amount if amount is not None else installment.amount
        installment.status = "paid"
        installment.paid_at = datetime.now(timezone.utc)
        installment.amount = confirmed_amount

        state = resolve_state(payment.status)
        state.on_installment_confirmed(payment, confirmed_amount)

        if payment.status == "paid":
            await self._on_payment_paid(payment)

    async def _fail_installment(
        self, installment: PaymentInstallment, payment: Payment, reason: str
    ) -> None:
        installment.status = "failed"
        installment.failure_reason = reason

        state = resolve_state(payment.status)
        state.on_installment_failed(payment, reason)

    async def _on_payment_paid(self, payment: Payment) -> None:
        """Effet de bord quand un paiement est complet."""
        if payment.payment_type == "wallet_topup":
            await self._credit_wallet(payment)
        # 'ride_payment' sera géré quand le paiement de course sera branché.

    async def _credit_wallet(self, payment: Payment) -> None:
        from app.core.config import settings
        from app.models.settings import SystemSettings
        from app.services.wallet import WalletService

        amount = payment.paid_amount

        # Bonus promo topup (settings système, pas .env)
        settings_row = (
            await self._db.execute(select(SystemSettings).limit(1))
        ).scalar_one_or_none()
        bonus = 0
        if settings_row and settings_row.topup_promo_active:
            bonus = round(amount * settings_row.topup_promo_rate / 100)

        first_installment = payment.installments[0] if payment.installments else None
        phone = first_installment.payer_phone if first_installment else None

        await WalletService(self._db).credit(
            payment.user_id,
            amount,
            "topup",
            bonus_amount=bonus,
            phone=phone,
            carrier=payment.provider,
            status="success",
        )

    async def _get_payment(self, payment_id: str) -> Payment:
        payment = await self._db.get(Payment, payment_id)
        if payment is None:
            raise HTTPException(404, "Paiement introuvable")
        return payment

    async def _get_installment_by_provider_id(
        self, provider_txn_id: str
    ) -> PaymentInstallment | None:
        result = await self._db.execute(
            select(PaymentInstallment)
            .options(
                selectinload(PaymentInstallment.payment).selectinload(Payment.installments)
            )
            .where(PaymentInstallment.provider_transaction_id == provider_txn_id)
        )
        return result.scalar_one_or_none()

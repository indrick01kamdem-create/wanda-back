from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.phone import detect_operator
from app.models.transaction import TX_STATUS_FAILED, TX_STATUS_PENDING, TX_STATUS_SUCCESS, TX_WITHDRAWAL, WalletTransaction
from app.services.payment.base import IPaymentProvider
from app.services.settings import SettingsService
from app.services.wallet import WalletService

logger = logging.getLogger(__name__)


class WithdrawalService:
    """
    Retraits : la demande est créée en PENDING, l'admin la traite.
    À l'approbation, un payout est initié auprès du provider (mock par défaut).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def request(self, user_id: str, amount: int, phone: str) -> WalletTransaction:
        settings = await SettingsService(self._db).get()
        if amount < settings.minimum_withdrawal:
            raise BadRequestException(
                f"Le retrait minimum est de {settings.minimum_withdrawal} FCFA"
            )

        wallet = await WalletService(self._db).get_or_create(user_id)
        if wallet.balance < amount:
            raise BadRequestException(
                f"Solde insuffisant : {wallet.balance} FCFA"
            )

        # Gèle le montant (débit immédiat, débité définitivement à l'approbation)
        wallet.balance -= amount
        self._db.add(
            WalletTransaction(
                wallet_id=wallet.id,
                user_id=user_id,
                type=TX_WITHDRAWAL,
                amount=-amount,
                phone=phone,
                carrier="manual",
                status=TX_STATUS_PENDING,
            )
        )
        await self._db.commit()
        return await self._latest_withdrawal(user_id)

    async def list_pending(self) -> list[WalletTransaction]:
        result = await self._db.execute(
            select(WalletTransaction)
            .where(
                WalletTransaction.type == TX_WITHDRAWAL,
                WalletTransaction.status == TX_STATUS_PENDING,
            )
            .order_by(WalletTransaction.created_at)
        )
        return list(result.scalars().all())

    async def approve(self, tx_id: str, provider: IPaymentProvider) -> WalletTransaction:
        tx = await self._get(tx_id)
        if tx.type != TX_WITHDRAWAL or tx.status != TX_STATUS_PENDING:
            raise BadRequestException("Transaction invalide")

        amount = abs(tx.amount)
        operator = detect_operator(tx.phone or "")
        medium = "orange money" if operator == "orange" else "mobile money"
        try:
            await provider.direct_pay(
                amount=amount,
                phone=tx.phone or "",
                medium=medium,
                order_id=tx.id,
                user_id=str(tx.user_id),
                message="Retrait Wanda",
            )
        except Exception as exc:
            logger.error("Withdrawal provider error: %s", exc)
            await self._refund(tx, "Échec du transfert du retrait")
            raise BadRequestException(f"Le transfert a échoué : {exc}. Le montant a été recrédité.")

        tx.status = TX_STATUS_SUCCESS
        await self._db.commit()
        await self._db.refresh(tx)
        return tx

    async def reject(self, tx_id: str) -> WalletTransaction:
        tx = await self._get(tx_id)
        if tx.type != TX_WITHDRAWAL or tx.status != TX_STATUS_PENDING:
            raise BadRequestException("Transaction invalide")
        await self._refund(tx, "Rejeté par l'administrateur")
        await self._db.commit()
        await self._db.refresh(tx)
        return tx

    async def _refund(self, tx: WalletTransaction, reason: str) -> None:
        tx.status = TX_STATUS_FAILED
        await WalletService(self._db).credit(
            tx.user_id,
            abs(tx.amount),
            "withdrawal_refund",
            carrier="wallet",
            status=TX_STATUS_SUCCESS,
        )

    async def _get(self, tx_id: str) -> WalletTransaction:
        tx = await self._db.get(WalletTransaction, tx_id)
        if tx is None:
            raise NotFoundException("Transaction introuvable")
        return tx

    async def _latest_withdrawal(self, user_id: str) -> WalletTransaction:
        result = await self._db.execute(
            select(WalletTransaction)
            .where(
                WalletTransaction.user_id == user_id,
                WalletTransaction.type == TX_WITHDRAWAL,
            )
            .order_by(WalletTransaction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one()

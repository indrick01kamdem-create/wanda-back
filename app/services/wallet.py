from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.transaction import WalletTransaction
from app.models.wallet import Wallet

logger = logging.getLogger(__name__)


class WalletService:
    """Solde FCFA + Wanda Points d'un utilisateur."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create(self, user_id: str) -> Wallet:
        result = await self._db.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )
        wallet = result.scalar_one_or_none()
        if wallet is not None:
            return wallet

        wallet = Wallet(user_id=user_id, balance=0, points=0)
        self._db.add(wallet)
        await self._db.flush()
        return wallet

    async def get(self, user_id: str) -> Wallet:
        result = await self._db.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )
        wallet = result.scalar_one_or_none()
        if wallet is None:
            raise NotFoundException("Portefeuille introuvable")
        return wallet

    async def credit(
        self,
        user_id: str,
        amount: int,
        type_: str,
        *,
        bonus_amount: int = 0,
        tip_amount: int = 0,
        phone: str | None = None,
        carrier: str = "wallet",
        status: str = "success",
        ride_id: str | None = None,
    ) -> WalletTransaction:
        if amount < 0:
            raise BadRequestException("Montant invalide")
        wallet = await self.get_or_create(user_id)
        if status == "success":
            wallet.balance += amount + bonus_amount

        tx = WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            type=type_,
            amount=amount,
            bonus_amount=bonus_amount,
            tip_amount=tip_amount,
            phone=phone,
            carrier=carrier,
            status=status,
            ride_id=ride_id,
        )
        self._db.add(tx)
        await self._db.commit()
        await self._db.refresh(tx)
        return tx

    async def debit(
        self,
        user_id: str,
        amount: int,
        type_: str,
        *,
        phone: str | None = None,
        carrier: str = "wallet",
        ride_id: str | None = None,
    ) -> WalletTransaction:
        if amount < 0:
            raise BadRequestException("Montant invalide")
        wallet = await self.get_or_create(user_id)
        if wallet.balance < amount:
            raise BadRequestException(
                f"Solde insuffisant : {wallet.balance} FCFA (besoin de {amount} FCFA)"
            )
        wallet.balance -= amount

        tx = WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            type=type_,
            amount=-amount,
            phone=phone,
            carrier=carrier,
            status="success",
            ride_id=ride_id,
        )
        self._db.add(tx)
        await self._db.commit()
        await self._db.refresh(tx)
        return tx

    async def add_points(self, user_id: str, points: int) -> None:
        if points <= 0:
            return
        wallet = await self.get_or_create(user_id)
        wallet.points += points

    async def redeem_points(self, user_id: str, points: int) -> int:
        """
        Convertit des points en FCFA (1 pt = 100 FCFA).
        Retourne le montant FCFA crédité, ou 0 si points invalides.
        """
        if points <= 0:
            return 0
        from app.core.config import settings

        value_per_point = settings.points_value_fcfa  # 100
        wallet = await self.get_or_create(user_id)
        usable = min(points, wallet.points)
        if usable <= 0:
            return 0
        wallet.points -= usable
        cash = usable * value_per_point
        wallet.balance += cash
        await self._db.commit()
        return cash

    async def list_transactions(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[WalletTransaction]:
        result = await self._db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

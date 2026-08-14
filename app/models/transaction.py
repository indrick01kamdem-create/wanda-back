import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

TX_TOPUP = "topup"
TX_WITHDRAWAL = "withdrawal"
TX_RIDE_PAYOUT = "ride_payout"
TX_COMMISSION_DEBIT = "commission_debit"
TX_RIDE_PAYMENT = "ride_payment"

TX_STATUS_SUCCESS = "success"
TX_STATUS_PENDING = "pending"
TX_STATUS_FAILED = "failed"

CARRIER_WALLET_DEBIT = "wallet_debit"
CARRIER_CASH_COMMISSION = "cash_commission"


class WalletTransaction(Base):
    """Append-only wallet ledger entry."""

    __tablename__ = "wallet_transactions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wallet_id: Mapped[str] = mapped_column(
        String, ForeignKey("wallets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tip_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    carrier: Mapped[str] = mapped_column(String(40), default="wallet", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=TX_STATUS_PENDING, nullable=False
    )
    ride_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="transactions")

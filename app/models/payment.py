import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Payment(Base):
    """
    Représente un paiement (wallet topup ou autre).
    Le statut suit un State pattern géré par PaymentService.
    """

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Type of payment: 'wallet_topup' | ...
    payment_type: Mapped[str] = mapped_column(String(30), default="wallet_topup", nullable=False)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Optional external reference (e.g. order/ride id)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)

    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 'pending' | 'partially_paid' | 'paid' | 'failed' | 'cancelled'
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)
    redirect_url: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    installments: Mapped[list["PaymentInstallment"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )


class PaymentInstallment(Base):
    """Représente une tranche de paiement (une seule pour un simple topup)."""

    __tablename__ = "payment_installments"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    payer_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    # 'pending' | 'paid' | 'failed' | 'cancelled'
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)

    # References from the payment provider (Fapshi transId, etc.)
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True, index=True
    )
    payment_url: Mapped[str | None] = mapped_column(String, nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    payment: Mapped["Payment"] = relationship(back_populates="installments")

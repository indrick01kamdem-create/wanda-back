from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_type: str
    user_id: str
    external_id: str | None = None
    total_amount: int
    paid_amount: int
    status: str
    provider: str
    redirect_url: str | None = None
    failure_reason: str | None = None
    created_at: datetime


class InstallmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payer_user_id: str | None = None
    payer_phone: str | None = None
    amount: int
    status: str
    provider: str
    provider_transaction_id: str | None = None
    payment_url: str | None = None
    paid_at: datetime | None = None


class PaymentDetailRead(PaymentRead):
    installments: list[InstallmentRead] = []


class SyncInstallmentRequest(BaseModel):
    installment_id: str

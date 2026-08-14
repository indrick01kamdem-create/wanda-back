from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WalletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    balance: int
    points: int


class WalletTopupRequest(BaseModel):
    amount: int
    phone: str
    provider: str | None = None  # mock | fapshi (défaut: config)
    redirect_url: str | None = None


class WalletTopupResponse(BaseModel):
    payment_id: str
    status: str
    payment_url: str | None = None
    ussd_code: str | None = None
    transaction_id: str | None = None
    amount: int
    bonus_rate: int = 0
    expected_bonus: int = 0


class WithdrawalRequest(BaseModel):
    amount: int
    phone: str


class WalletTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    amount: int
    bonus_amount: int
    tip_amount: int
    phone: str | None = None
    carrier: str
    status: str
    ride_id: str | None = None
    created_at: datetime

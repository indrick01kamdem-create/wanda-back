from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class PaymentInitResponse(BaseModel):
    transaction_id: str
    payment_url: str | None = None
    ussd_code: str | None = None  # *144# etc.
    reference: str
    amount: int
    currency: str = "FCFA"
    provider: str
    expires_at: str  # ISO datetime


class PaymentStatus(BaseModel):
    transaction_id: str
    status: str  # 'pending' | 'paid' | 'failed' | 'cancelled'
    amount: int | None = None
    paid_at: str | None = None


class WebhookEvent(BaseModel):
    """
    Représentation normalisée d'un événement webhook,
    indépendante du provider.
    """
    transaction_id: str           # transId
    status: str                   # normalized: 'pending' | 'paid' | 'failed'
    amount: Optional[int] = None
    payer_name: Optional[str] = None
    payer_email: Optional[str] = None
    external_id: Optional[str] = None   # notre order_id
    financial_trans_id: Optional[str] = None
    date_confirmed: Optional[str] = None
    raw: dict = {}                # payload brut conservé pour audit


class IPaymentProvider(ABC):
    @abstractmethod
    async def initiate(
        self, amount: int, phone: str, order_id: str
    ) -> PaymentInitResponse: ...

    @abstractmethod
    async def direct_pay(
        self,
        amount: int,
        phone: str,
        medium: str,
        order_id: str,
        user_id: str = "",
        message: str = "",
    ) -> PaymentInitResponse: ...

    @abstractmethod
    async def verify(self, transaction_id: str) -> PaymentStatus: ...

    @abstractmethod
    async def refund(
        self, transaction_id: str, amount: int | None = None
    ) -> bool: ...

    @abstractmethod
    def parse_webhook(self, payload: dict) -> WebhookEvent:
        """
        Transforme le payload brut du provider en WebhookEvent normalisé.
        Appelé par le router avant de passer l'événement au PaymentService.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

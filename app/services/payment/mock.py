import uuid
from datetime import datetime, timedelta, timezone

from app.services.payment.base import IPaymentProvider, PaymentInitResponse, PaymentStatus, WebhookEvent


class MockPaymentProvider(IPaymentProvider):
    """Simule un paiement réussi pour la Phase 1"""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def initiate(
        self, amount: int, phone: str, order_id: str
    ) -> PaymentInitResponse:
        return PaymentInitResponse(
            transaction_id=f"mock_{uuid.uuid4().hex[:8]}",
            ussd_code="*144#",
            reference=f"WD-{order_id[:8].upper()}",
            amount=amount,
            provider="mock",
            expires_at=(
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        )

    async def direct_pay(
        self,
        amount: int,
        phone: str,
        medium: str,
        order_id: str,
        user_id: str = "",
        message: str = "",
    ) -> PaymentInitResponse:
        return PaymentInitResponse(
            transaction_id=f"mock_{uuid.uuid4().hex[:8]}",
            ussd_code="*144#",
            reference=f"WD-{order_id[:8].upper()}",
            amount=amount,
            provider="mock",
            expires_at=(
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        )

    async def verify(self, transaction_id: str) -> PaymentStatus:
        # Simule toujours un succès
        return PaymentStatus(
            transaction_id=transaction_id,
            status="paid",
            amount=None,
            paid_at=datetime.now(timezone.utc).isoformat(),
        )

    async def refund(
        self, transaction_id: str, amount: int | None = None
    ) -> bool:
        return True

    def parse_webhook(self, payload: dict) -> WebhookEvent:
        return WebhookEvent(
            transaction_id=payload.get("transId", ""),
            status="paid",
            amount=payload.get("amount"),
            raw=payload,
        )

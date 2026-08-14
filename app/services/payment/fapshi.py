"""
Fapshi Payment Provider — implémentation de IPaymentProvider.

Respecte SOLID:
  - S: ce fichier ne fait que communiquer avec l'API Fapshi.
  - O: de nouveaux comportements (retry, logging) s'ajoutent par composition.
  - L: substituable partout où IPaymentProvider est attendu.
  - I: implémente uniquement l'interface minimale IPaymentProvider.
  - D: le service dépend de IPaymentProvider, pas de cette classe directement.

Référence API Fapshi:
  Base URL : https://live.fapshi.com  (ou https://sandbox.fapshi.com en test)
  Headers  : apiuser, apikey
  POST /initiate-pay   → { amount, email, redirectUrl, userId, externalId }
  GET  /payment-status/{transId}
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.services.payment.base import IPaymentProvider, PaymentInitResponse, PaymentStatus, WebhookEvent

logger = logging.getLogger(__name__)

# Fapshi payment statuses → normalized
_STATUS_MAP = {
    "INITIATED": "pending",
    "PENDING": "pending",
    "SUCCESSFUL": "paid",
    "FAILED": "failed",
    "EXPIRED": "failed",
}


class FapshiProvider(IPaymentProvider):
    """Passerelle vers l'API Fapshi (Mobile Money Cameroun)."""

    def __init__(self) -> None:
        self._base_url = settings.fapshi_base_url.rstrip("/")
        self._headers = {
            "apiuser": settings.fapshi_api_user,
            "apikey": settings.fapshi_api_key,
            "Content-Type": "application/json",
        }

    @property
    def provider_name(self) -> str:
        return "fapshi"

    # ─────────────────────────────────────────────────────────────────────────
    # IPaymentProvider
    # ─────────────────────────────────────────────────────────────────────────

    async def initiate(
        self, amount: int, phone: str, order_id: str
    ) -> PaymentInitResponse:
        """
        Initie un paiement et retourne le lien de paiement Fapshi.
        `phone` est utilisé comme userId Fapshi.
        `order_id` est l'externalId pour la réconciliation.
        """
        payload = {
            "amount": amount,
            "externalId": order_id,
            "redirectUrl": settings.fapshi_redirect_url,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/initiate-pay",
                json=payload,
                headers=self._headers,
            )

        data = self._parse_response(response, "initiate")
        trans_id: str = data["transId"]
        payment_url: str = data.get("link", "")

        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        logger.info("Fapshi payment initiated: transId=%s amount=%d", trans_id, amount)

        return PaymentInitResponse(
            transaction_id=trans_id,
            payment_url=payment_url,
            reference=trans_id,
            amount=amount,
            provider=self.provider_name,
            expires_at=expires_at,
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
        """
        Initie un paiement direct (sans redirection) via Fapshi /direct-pay.
        `phone` est le numéro MTN ou Orange du payeur.
        `medium` est 'mobile money' ou 'orange money'.
        `order_id` est l'externalId pour la réconciliation.
        """
        # Normalise vers 6XXXXXXXX (Fapshi attend le numéro sans indicatif pays)
        phone_digits = "".join(c for c in phone if c.isdigit())
        if phone_digits.startswith("237"):
            phone_digits = phone_digits[3:]
        phone = phone_digits

        payload: dict = {
            "amount": amount,
            "phone": phone,
            "medium": medium,
            "name": "wanda",
            "email": "contact@wanda.app",
            "externalId": order_id,
        }
        if user_id:
            payload["userId"] = user_id
        if message:
            payload["message"] = message

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/direct-pay",
                json=payload,
                headers=self._headers,
            )

        data = self._parse_response(response, "direct_pay")
        trans_id: str = data["transId"]
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        logger.info("Fapshi direct-pay initiated: transId=%s amount=%d phone=%s", trans_id, amount, phone)

        return PaymentInitResponse(
            transaction_id=trans_id,
            payment_url=None,
            reference=order_id,
            amount=amount,
            provider=self.provider_name,
            expires_at=expires_at,
        )

    async def verify(self, transaction_id: str) -> PaymentStatus:
        """Interroge Fapshi pour connaître le statut d'une transaction."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/payment-status/{transaction_id}",
                headers=self._headers,
            )

        data = self._parse_response(response, "verify")
        raw_status: str = data.get("status", "PENDING")
        normalized = _STATUS_MAP.get(raw_status.upper(), "pending")

        paid_at: str | None = None
        if normalized == "paid":
            paid_at = data.get("paidAt") or datetime.now(timezone.utc).isoformat()

        return PaymentStatus(
            transaction_id=transaction_id,
            status=normalized,
            amount=data.get("amount"),
            paid_at=paid_at,
        )

    async def refund(self, transaction_id: str, amount: int | None = None) -> bool:
        """
        Fapshi ne propose pas encore d'endpoint de remboursement automatique.
        À implémenter manuellement via le dashboard Fapshi ou un endpoint futur.
        """
        logger.warning(
            "Fapshi refund requested for %s — manual action required in dashboard.",
            transaction_id,
        )
        return False

    def parse_webhook(self, payload: dict) -> WebhookEvent:
        """
        Transforme le payload brut Fapshi en WebhookEvent normalisé.
        Fapshi envoie un tableau — le router passe le premier élément ici.
        """
        return WebhookEvent(
            transaction_id=payload["transId"],
            status=_STATUS_MAP.get(payload.get("status", "").upper(), "pending"),
            amount=payload.get("amount"),
            payer_name=payload.get("payerName"),
            payer_email=payload.get("email"),
            external_id=payload.get("externalId"),
            financial_trans_id=payload.get("financialTransId"),
            date_confirmed=payload.get("dateConfirmed"),
            raw=payload,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_response(self, response: httpx.Response, action: str) -> dict:
        """
        Analyse la réponse Fapshi.
        Fapshi renvoie soit { "message": "ok", "data": {...} }
        soit directement l'objet à la racine (selon la version de l'API).
        Lève une ValueError si le status HTTP indique une erreur.
        """
        try:
            body = response.json()
        except Exception:
            raise ValueError(
                f"Fapshi {action}: réponse non-JSON (HTTP {response.status_code})"
            )

        if response.status_code not in (200, 201):
            message = body.get("message") or body.get("error") or str(body)
            raise ValueError(
                f"Fapshi {action} échoué (HTTP {response.status_code}): {message}"
            )

        # Certaines versions de l'API Fapshi encapsulent dans "data"
        return body.get("data") or body

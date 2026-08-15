"""
Provider SMS â€” TextBee (via gateway Android)
POST https://{base_url}/api/v1/gateway/devices/{device_id}/send-sms
Header : x-api-key: {api_key}
Body   : { "subscriptionId": 4|5, "recipients": [phone], "message": "..." }

subscriptionId : 4 = SIM Orange, 5 = SIM MTN
DÃ©tection automatique depuis le prÃ©fixe camerounais :
  - Orange : 69x
  - MTN    : 65x, 67x
  - Autre  â†’ dÃ©lÃ©gation au provider de fallback

En cas d'Ã©chec rÃ©seau ou de rÃ©ponse non-2xx, fallback vers le provider configurÃ©.
"""

import hashlib
import logging
import re

import httpx

from app.core.config import settings
from .base import SMSProvider

logger = logging.getLogger(__name__)

OTP_EXPIRE_MINUTES = 10

SMS_TEMPLATE = (
    "Wanda Taxi\n"
    "Inscription reussie {code}\n"
    "Code de verification"
)


_MTN_RE = re.compile(r"^6(([78][0-9]{7})|(5[0-4][0-9]{6}))$")
_ORANGE_RE = re.compile(r"^6((9[0-9]{7})|(5[5-9][0-9]{6}))$")


def _detect_operator(phone: str) -> str | None:
    """
    DÃ©tecte l'opÃ©rateur camerounais depuis un numÃ©ro international.
    Retourne "orange", "mtn", ou None si non reconnu.

    MTN    : 67x, 68x, 650-654
    Orange : 69x, 655-659
    """
    normalized = phone.replace(" ", "").replace("-", "")
    if normalized.startswith("+237"):
        local = normalized[4:]
    elif normalized.startswith("237"):
        local = normalized[3:]
    else:
        local = normalized

    if _MTN_RE.match(local):
        return "mtn"
    if _ORANGE_RE.match(local):
        return "orange"
    return None


class TextBeeProvider(SMSProvider):
    """
    Provider principal si SMS_PROVIDER=textbee.
    Utilise TextBee pour Orange et MTN.
    DÃ©lÃ¨gue au fallback pour les autres opÃ©rateurs ou en cas d'Ã©chec.
    """

    def __init__(self, fallback: SMSProvider) -> None:
        self.fallback = fallback

    async def send(self, phone: str, code: str) -> None:
        operator = _detect_operator(phone)

        if operator is None:
            logger.info(
                "TextBee: opÃ©rateur non reconnu pour %s â€” dÃ©lÃ©gation au fallback",
                phone[:6] + "****",
            )
            await self.fallback.send(phone, code)
            return

        subscription_id = (
            settings.textbee_subscription_id_orange
            if operator == "orange"
            else settings.textbee_subscription_id_mtn
        )

        url = (
            f"{settings.textbee_base_url}/api/v1/gateway/devices"
            f"/{settings.textbee_device_id}/send-sms"
        )
        headers = {"x-api-key": settings.textbee_api_key}
        payload = {
            "subscriptionId": subscription_id,
            "recipients": [phone],
            "message": SMS_TEMPLATE.format(code=code, minutes=OTP_EXPIRE_MINUTES),
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                logger.info(
                    "TextBee: SMS envoyÃ© Ã  %s (opÃ©rateur=%s, subscriptionId=%s)",
                    phone[:6] + "****",
                    operator,
                    subscription_id,
                )
        except Exception as exc:
            logger.warning(
                "TextBee: Ã©chec pour %s (%s) â€” fallback activÃ©",
                phone[:6] + "****",
                exc,
            )
            await self.fallback.send(phone, code)

    async def verify(self, phone: str, code: str, stored_hash: str) -> bool:
        # Validation locale â€” identique Ã  AvlyText
        return hashlib.sha256(code.encode()).hexdigest() == stored_hash

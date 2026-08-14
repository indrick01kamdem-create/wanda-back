"""
Provider SMS â€” AvlyText
POST https://api.avlytext.com/v1/sms?api_key={api_key}
Body JSON : { sender, recipient, text }

La validation OTP est locale (hash SHA-256).
"""

import hashlib
import logging

import httpx

from app.core.config import settings
from .base import SMSProvider

logger = logging.getLogger(__name__)

OTP_EXPIRE_MINUTES = 10

SMS_TEMPLATE = (
    "Wanda\n"
    "Inscription reussie {code}\n"
    "Code de vÃ©rification"
)


class AvlyTextProvider(SMSProvider):

    async def send(self, phone: str, code: str) -> None:
        if not settings.avlytext_api_key:
            logger.warning("AVLYTEXT_API_KEY absent â€” OTP %s : %s", phone[:4] + "****", code)
            return

        url = f"https://api.avlytext.com/v1/sms?api_key={settings.avlytext_api_key}"
        payload = {
            "sender": settings.avlytext_sender,
            "recipient": phone,
            "text": SMS_TEMPLATE.format(code=code, minutes=OTP_EXPIRE_MINUTES),
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("AvlyText: SMS envoyÃ© Ã  %s", phone[:4] + "****")

    async def verify(self, phone: str, code: str, stored_hash: str) -> bool:
        # Validation locale â€” AvlyText ne valide pas cÃ´tÃ© serveur
        return hashlib.sha256(code.encode()).hexdigest() == stored_hash

"""
Provider SMS â€” Twilio
- Envoi via Twilio Verify (si TWILIO_VERIFY_SID configurÃ©)
- Validation cÃ´tÃ© serveur Twilio Verify
- Fallback local si Verify Ã©choue
"""

import asyncio
import hashlib
import logging
from functools import partial

from app.core.config import settings
from .base import SMSProvider

logger = logging.getLogger(__name__)


class TwilioProvider(SMSProvider):

    async def send(self, phone: str, code: str) -> None:
        if not settings.twilio_account_sid:
            logger.warning("Twilio non configurÃ© â€” OTP %s", phone[:4] + "****")
            return

        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        loop = asyncio.get_event_loop()

        if settings.twilio_verify_sid:
            try:
                await loop.run_in_executor(
                    None,
                    partial(
                        client.verify.v2.services(settings.twilio_verify_sid)
                        .verifications.create,
                        to=phone,
                        channel="sms",
                    ),
                )
                logger.info("Twilio Verify: SMS envoyÃ© Ã  %s", phone[:4] + "****")
                return
            except Exception:
                logger.exception("Twilio Verify Ã©chouÃ©, fallback Messages API")

        if not settings.twilio_phone_number:
            logger.error("TWILIO_PHONE_NUMBER absent, impossible d'envoyer le SMS")
            return

        body = (
            f"Wanda - Code de vÃ©rification : {code}\n"
            f"Valable 10 min. Ne le partagez pas."
        )
        await loop.run_in_executor(
            None,
            partial(
                client.messages.create,
                body=body,
                from_=settings.twilio_phone_number,
                to=phone,
            ),
        )

    async def verify(self, phone: str, code: str, stored_hash: str) -> bool:
        # Essai cÃ´tÃ© serveur Twilio Verify
        if settings.twilio_verify_sid and settings.twilio_account_sid:
            result = await self._verify_via_twilio(phone, code)
            if result is not None:
                return result

        # Fallback local
        return hashlib.sha256(code.encode()).hexdigest() == stored_hash

    @staticmethod
    async def _verify_via_twilio(phone: str, code: str) -> bool | None:
        import asyncio
        from functools import partial
        from twilio.rest import Client

        try:
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            loop = asyncio.get_event_loop()
            check = await loop.run_in_executor(
                None,
                partial(
                    client.verify.v2.services(settings.twilio_verify_sid)
                    .verification_checks.create,
                    to=phone,
                    code=code,
                ),
            )
            return check.status == "approved"
        except Exception:
            logger.exception("Twilio Verify check Ã©chouÃ©, fallback local")
            return None

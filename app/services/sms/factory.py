"""
Factory — retourne le provider SMS actif selon SMS_PROVIDER dans .env.
"""

from app.core.config import settings
from .base import SMSProvider


def _get_basic_provider(name: str) -> SMSProvider:
    """Instancie un provider de base (sans fallback)."""
    if name == "twilio":
        from .twilio_provider import TwilioProvider
        return TwilioProvider()
    if name == "avlytext":
        from .avlytext_provider import AvlyTextProvider
        return AvlyTextProvider()
    raise ValueError(f"SMS_PROVIDER inconnu : '{name}'. Valeurs valides : twilio, avlytext, textbee")


def get_sms_provider() -> SMSProvider:
    provider = settings.sms_provider.lower()

    if provider == "textbee":
        from .textbee_provider import TextBeeProvider
        fallback = _get_basic_provider(settings.textbee_fallback_provider)
        return TextBeeProvider(fallback=fallback)

    return _get_basic_provider(provider)

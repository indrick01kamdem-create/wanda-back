from app.core.config import settings
from app.services.payment.base import IPaymentProvider
from app.services.payment.fapshi import FapshiProvider
from app.services.payment.mock import MockPaymentProvider


class PaymentFactory:
    _providers: dict[str, type[IPaymentProvider]] = {
        "mock": MockPaymentProvider,
        "fapshi": FapshiProvider,
    }

    @classmethod
    def get_provider(cls, provider_name: str | None = None) -> IPaymentProvider:
        name = provider_name or settings.payment_provider
        provider_class = cls._providers.get(name, MockPaymentProvider)
        return provider_class()

    @classmethod
    def get_default(cls) -> IPaymentProvider:
        return cls.get_provider()

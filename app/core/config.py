from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database.
    database_url: str

    # JWT
    secret_key: str
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 30
    refresh_token_expire_minutes: int = 43200  # 30 jours
    algorithm: str = "HS256"

    # Cloudinary
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # SMS provider: "twilio" | "avlytext" | "textbee"
    sms_provider: str = "avlytext"

    # Twilio (OTP SMS)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_verify_sid: str = ""

    # AvlyText (OTP SMS)
    avlytext_api_key: str = ""
    avlytext_sender: str = "Wanda"

    # TextBee (OTP SMS via gateway Android)
    textbee_base_url: str = ""
    textbee_api_key: str = ""
    textbee_device_id: str = ""
    textbee_subscription_id_orange: int = 4
    textbee_subscription_id_mtn: int = 5
    textbee_fallback_provider: str = "avlytext"

    # App
    app_env: str = "development"
    app_name: str = "Wanda API"
    app_version: str = "1.0.0"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Payment
    payment_provider: str = "mock"

    # Fapshi
    fapshi_api_user: str = ""
    fapshi_api_key: str = ""
    fapshi_base_url: str = "https://live.fapshi.com"
    fapshi_sandbox_url: str = "https://sandbox.fapshi.com"
    fapshi_redirect_url: str = ""
    fapshi_webhook_secret: str = ""

    # Wanda pricing defaults (mirror src/data.ts + useSystemSettings.ts)
    default_commission_rate: int = 15
    default_surge_multiplier: float = 1.0
    default_minimum_withdrawal: int = 2000
    default_topup_promo_active: bool = True
    default_topup_promo_rate: int = 20
    wallet_discount_pct: int = 15          # wallet pays 15% less
    points_value_fcfa: int = 100           # 1 Wanda Point = 100 FCFA
    point_per_wallet_ride: int = 1         # 1 point earned per wallet-paid ride
    waiting_grace_seconds: int = 10
    waiting_rate_per_second: int = 100

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

# Numéro camerounais : +237 + 9 chiffres (6XXXXXXXX, MTN/Orange).
# Les formes locales (237... / 6...) sont normalisées en E.164 avant validation.
_PHONE_RE = re.compile(r"^\+2376[256789]\d{7}$")


def normalize_phone(v: str) -> str:
    v = v.strip().replace(" ", "").replace("-", "")
    if v.startswith("+237"):
        return v
    if v.startswith("237"):
        return "+" + v
    if v.startswith("6"):
        return "+237" + v
    return v


class SendOTPRequest(BaseModel):
    """Étape 1 : l'utilisateur envoie son numéro pour recevoir le SMS."""
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = normalize_phone(v)
        if not _PHONE_RE.match(v):
            raise ValueError("Numéro camerounais invalide : +2376XXXXXXXX ou 6XXXXXXXX")
        return v


class VerifyOTPRequest(BaseModel):
    """Étape 2 : l'utilisateur soumet le code reçu par SMS."""
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{6}$", v):
            raise ValueError("Le code doit contenir exactement 6 chiffres")
        return v


class OTPSentResponse(BaseModel):
    message: str = "Code envoyé par SMS"
    phone: str


# ── Admin login ───────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    """Connexion admin par e-mail et mot de passe."""
    email: str
    password: str


# ── Token / Session ───────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False
    user: "UserRead"


class RefreshRequest(BaseModel):
    refresh_token: str


# Avoid circular import
from app.schemas.user import UserRead  # noqa: E402

TokenResponse.model_rebuild()

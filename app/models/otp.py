import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PhoneOTP(Base):
    """
    Code OTP envoyé par SMS pour l'authentification.

    Règles de sécurité :
    - Le code est stocké hashé (SHA-256), jamais en clair.
    - Expire après 10 minutes.
    - Invalidé après 5 tentatives incorrectes (attempt_count).
    - Un seul OTP actif par numéro (les anciens sont marqués is_used=True à l'envoi).
    - Rate limit : 1 SMS max par numéro toutes les 60 secondes (vérifié côté service).
    """

    __tablename__ = "phone_otps"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Code hashé SHA-256 (jamais le code en clair)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Nombre de tentatives de vérification incorrectes
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

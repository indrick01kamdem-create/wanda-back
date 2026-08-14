import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

USER_ROLE_PASSENGER = "passenger"
USER_ROLE_DRIVER = "driver"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Identifiant principal : numéro de téléphone (OTP) ─────────────────────
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Profil ────────────────────────────────────────────────────────────────
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # 'passenger' | 'driver'
    role: Mapped[str] = mapped_column(
        String(20), default=USER_ROLE_PASSENGER, nullable=False
    )
    # Camerounese cities: 'Yaoundé' | 'Douala' | ...
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slang_mode: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Mot de passe : nullable car auth = OTP uniquement (admin l'utilise) ──
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Driver-only reference (1:1) ───────────────────────────────────────────
    driver_profile: Mapped["DriverProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # ── Wallet (1:1) ──────────────────────────────────────────────────────────
    wallet: Mapped["Wallet | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Admin role: 'super_admin' | 'accounting' | 'publicity' | 'forensic'
    admin_role: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    rides_as_passenger: Mapped[list["Ride"]] = relationship(
        back_populates="passenger", foreign_keys="Ride.passenger_id"
    )
    rides_as_driver: Mapped[list["Ride"]] = relationship(
        back_populates="driver", foreign_keys="Ride.driver_id"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE")
    )
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

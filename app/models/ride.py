import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

RIDE_STATUS_SEARCHING = "searching"
RIDE_STATUS_DRIVER_FOUND = "driver_found"
RIDE_STATUS_ARRIVING = "arriving"
RIDE_STATUS_IN_PROGRESS = "in_progress"
RIDE_STATUS_COMPLETED = "completed"
RIDE_STATUS_CANCELLED = "cancelled"

# Payment methods (mirror src/types/wallet.ts)
PAYMENT_MOMO_MTN = "momo_mtn"
PAYMENT_ORANGE_MONEY = "orange_money"
PAYMENT_CASH = "cash"
PAYMENT_WALLET = "wallet"

# Ride classes (mirror src/data.ts)
RIDE_CLASS_IDS = ["okada", "keke", "ecoride", "comfort"]


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    passenger_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    driver_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    passenger_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    passenger_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Location objects as JSON { name, lat, lng }
    pickup: Mapped[dict] = mapped_column(JSON, nullable=False)
    destination: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Fare / pricing
    ride_class_id: Mapped[str] = mapped_column(
        String(30), default="ecoride", nullable=False
    )
    fare: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # final fare charged
    base_fare: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    surge_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    waiting_fare: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tip_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points_redeemed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    commission_rate: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    platform_commission: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    driver_net_earnings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    payment_method: Mapped[str] = mapped_column(
        String(30), default=PAYMENT_WALLET, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default=RIDE_STATUS_SEARCHING, nullable=False, index=True
    )

    # Cancellation (see src/types/ride.ts CancelReason)
    cancel_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Waiting time tracking
    waiting_time_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ratings (given at completion)
    passenger_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passenger_praise: Mapped[str | None] = mapped_column(String, nullable=True)

    # Wallet topup reference for payment (mobile money)
    payment_transaction_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    passenger: Mapped["User"] = relationship(
        back_populates="rides_as_passenger", foreign_keys=[passenger_id]
    )
    driver: Mapped["User | None"] = relationship(
        back_populates="rides_as_driver", foreign_keys=[driver_id]
    )
    location_updates: Mapped[list["RideLocationUpdate"]] = relationship(
        back_populates="ride", cascade="all, delete-orphan", order_by="RideLocationUpdate.created_at"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="ride", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class RideLocationUpdate(Base):
    """Live GPS updates pushed by the driver during a ride."""

    __tablename__ = "ride_location_updates"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    ride_id: Mapped[str] = mapped_column(
        String, ForeignKey("rides.id", ondelete="CASCADE"), index=True
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ride: Mapped["Ride"] = relationship(back_populates="location_updates")


class ChatMessage(Base):
    """In-ride chat between passenger and driver."""

    __tablename__ = "ride_chat_messages"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    ride_id: Mapped[str] = mapped_column(
        String, ForeignKey("rides.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False)  # passenger | driver
    text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ride: Mapped["Ride"] = relationship(back_populates="chat_messages")


class RideShareToken(Base):
    """Public live-tracking share token for a ride."""

    __tablename__ = "ride_share_tokens"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    ride_id: Mapped[str] = mapped_column(
        String, ForeignKey("rides.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

HISTORY_COMPLETED = "completed"
HISTORY_CANCELLED = "cancelled"


class RideHistory(Base):
    """Ride history entry, owned by a user (passenger side, as in the app)."""

    __tablename__ = "ride_history"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ride_id: Mapped[str | None] = mapped_column(String, nullable=True)

    pickup_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pickup_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    pickup_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    dest_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    dest_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    fare: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tip_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="wallet", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=HISTORY_COMPLETED, nullable=False
    )
    vehicle_class: Mapped[str] = mapped_column(String(30), default="ecoride", nullable=False)
    driver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points_redeemed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()

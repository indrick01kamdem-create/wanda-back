import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemSettings(Base):
    """Singleton row: settings/pricing (commission, surge, class rates, promo)."""

    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default="pricing"
    )
    commission_rate: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    surge_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    minimum_withdrawal: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    topup_promo_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    topup_promo_rate: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    # JSON: { "okada": {baseFare, perKm}, "keke": {...}, "ecoride": {...}, "comfort": {...} }
    class_rates: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Notification(Base):
    """Broadcast notification, targeted at 'all' | 'passenger' | 'driver'."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    target: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    # 'promo' | 'info' | 'alert' | 'route_fare'
    type: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="fr", nullable=False)
    # JSON route data for route_fare notifications
    route_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # JSON list of user ids who read it
    read_by: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NotificationSchedule(Base):
    """Singleton row: settings/notification_schedule (daily templates + times)."""

    __tablename__ = "notification_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    times_per_day: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    # JSON: ["08:00", "12:30", "18:00"]
    times_list: Mapped[list | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="fr", nullable=False)
    # JSON: { passengerTemplates: [{title, message, includeRouteFare?}], driverTemplates: [...] }
    templates: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

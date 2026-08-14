import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

KYC_DOC_KEYS = [
    "nationalIdFront",
    "nationalIdBack",
    "driverLicense",
    "vehicleInsurance",
    "vehicleGreyCard",
]

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_SUSPENDED = "suspended"

KYC_VERIFIED = "verified"
KYC_REJECTED = "rejected"

DRIVER_STATUS_IDLE = "idle"
DRIVER_STATUS_HEADING_PICKUP = "heading_to_pickup"
DRIVER_STATUS_ARRIVED_PICKUP = "arrived_pickup"
DRIVER_STATUS_DRIVING = "driving_to_destination"
DRIVER_STATUS_OFFLINE = "offline"


class DriverProfile(Base):
    """Extension 1:1 de User quand role == 'driver'."""

    __tablename__ = "driver_profiles"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Vehicle
    vehicle_type: Mapped[str] = mapped_column(String(30), default="ecoride")  # okada | keke | ecoride | comfort
    vehicle_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vehicle_color: Mapped[str | None] = mapped_column(String(60), nullable=True)
    vehicle_plate: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Approval / KYC
    approval_status: Mapped[str] = mapped_column(
        String(20), default=APPROVAL_PENDING, nullable=False
    )
    kyc_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    # JSON: { docKey: { title, url, updatedByAdmin, updatedAt, status, adminNote? } }
    kyc_documents: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Live presence (dispatcher)
    status: Mapped[str] = mapped_column(
        String(30), default=DRIVER_STATUS_OFFLINE, nullable=False
    )
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)

    # Local display fields edited by admin (not persisted to Firestore — kept here)
    cnic_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="driver_profile")

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class KYC_Document(BaseModel):
    title: str
    url: str
    updatedByAdmin: bool = False
    updatedAt: str | None = None
    status: str = "pending"  # pending | verified | rejected
    adminNote: str | None = None


class DriverProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    user_name: str | None = None
    user_phone: str | None = None
    vehicle_type: str
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    vehicle_plate: str | None = None
    approval_status: str
    kyc_status: str | None = None
    rejection_reason: str | None = None
    rating: float
    kyc_documents: dict[str, KYC_Document] | None = None
    status: str
    lat: float | None = None
    lng: float | None = None
    is_online: bool
    created_at: datetime


class DriverApprovalUpdate(BaseModel):
    approval_status: str  # approved | pending | suspended
    rejection_reason: str | None = None


class DriverKYCUpdate(BaseModel):
    kyc_status: str  # verified | rejected | pending
    kyc_documents: dict[str, KYC_Document] | None = None


class DriverLocationUpdate(BaseModel):
    lat: float
    lng: float
    is_online: bool | None = None
    status: str | None = None


class DriverEditRequest(BaseModel):
    vehicle_type: str | None = None
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    vehicle_plate: str | None = None
    cnic_number: str | None = None
    license_number: str | None = None
    kyc_documents: dict[str, KYC_Document] | None = None
    name: str | None = None
    phone: str | None = None


class OnlineDriverRead(BaseModel):
    """Chauffeur disponible (approuvé + en ligne + position) exposé publiquement
    pour la carte passager — sans données sensibles."""

    user_id: str
    name: str
    phone: str | None = None
    vehicle_type: str
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    vehicle_plate: str | None = None
    rating: float
    lat: float | None = None
    lng: float | None = None

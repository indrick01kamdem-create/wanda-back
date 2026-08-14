from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GeoPoint(BaseModel):
    name: str = ""
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RideEstimateRequest(BaseModel):
    pickup: GeoPoint
    destination: GeoPoint
    ride_class_id: str = "ecoride"


class RideEstimateResponse(BaseModel):
    ride_class_id: str
    distance_km: float
    base_fare: int
    per_km: int
    fare: int
    surge_multiplier: float
    estimated_duration_min: int


class CreateRideRequest(BaseModel):
    pickup: GeoPoint
    destination: GeoPoint
    ride_class_id: str = "ecoride"
    payment_method: str = "wallet"  # momo_mtn | orange_money | cash | wallet
    tip_amount: int = 0
    points_redeemed: int = 0


class RideLocationUpdateRequest(BaseModel):
    lat: float
    lng: float


class RideShareResponse(BaseModel):
    token: str
    lat: float | None = None
    lng: float | None = None
    status: str
    passenger_name: str | None = None
    driver_name: str | None = None
    vehicle_plate: str | None = None
    vehicle_type: str | None = None
    vehicle_color: str | None = None
    driver_rating: float | None = None


class RideRatingRequest(BaseModel):
    passenger_rating: int = Field(ge=1, le=5)
    passenger_praise: str | None = None


class RideCancelRequest(BaseModel):
    reason: str | None = None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_id: str | None = None
    sender_role: str
    text: str
    created_at: datetime


class ChatMessageCreate(BaseModel):
    ride_id: str
    text: str


class RideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    passenger_id: str
    driver_id: str | None = None
    passenger_name: str | None = None
    passenger_phone: str | None = None
    pickup: dict
    destination: dict
    ride_class_id: str
    fare: int
    base_fare: int
    distance_km: float
    surge_multiplier: float
    waiting_fare: int
    tip_amount: int
    points_redeemed: int
    points_earned: int
    commission_rate: int
    platform_commission: int
    driver_net_earnings: int
    payment_method: str
    status: str
    cancel_reason: str | None = None
    cancelled_by: str | None = None
    waiting_time_seconds: int
    passenger_rating: int | None = None
    passenger_praise: str | None = None
    created_at: datetime
    updated_at: datetime

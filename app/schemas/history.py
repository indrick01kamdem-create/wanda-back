from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RideHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    ride_id: str | None = None
    pickup_name: str
    dest_name: str
    pickup_lat: float | None = None
    pickup_lng: float | None = None
    dest_lat: float | None = None
    dest_lng: float | None = None
    fare: int
    tip_amount: int
    payment_method: str
    status: str
    vehicle_class: str
    driver_name: str | None = None
    points_earned: int
    points_redeemed: int
    created_at: datetime

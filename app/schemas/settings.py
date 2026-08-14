from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClassRate(BaseModel):
    baseFare: int
    perKm: int
    label: str | None = None


class SystemSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commission_rate: int
    surge_multiplier: float
    minimum_withdrawal: int
    topup_promo_active: bool
    topup_promo_rate: int
    class_rates: dict[str, ClassRate] | None = None
    updated_at: datetime | None = None


class SystemSettingsUpdate(BaseModel):
    commission_rate: int | None = None
    surge_multiplier: float | None = None
    minimum_withdrawal: int | None = None
    topup_promo_active: bool | None = None
    topup_promo_rate: int | None = None
    class_rates: dict[str, ClassRate] | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target: str
    title: str
    message: str
    type: str
    language: str
    route_data: dict | None = None
    read_by: list | None = None
    created_at: datetime


class NotificationCreate(BaseModel):
    target: str = "all"  # all | passenger | driver
    title: str
    message: str
    type: str = "info"
    language: str = "fr"
    route_data: dict | None = None


class NotificationScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    times_per_day: int
    times_list: list | None = None
    language: str
    templates: dict | None = None


class NotificationScheduleUpdate(BaseModel):
    enabled: bool | None = None
    times_per_day: int | None = None
    times_list: list | None = None
    language: str | None = None
    templates: dict | None = None

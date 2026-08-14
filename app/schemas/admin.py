from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    email: str
    name: str | None = None
    role: str
    department_name: str | None = None
    assigned_by: str | None = None
    active: bool
    created_at: datetime


class AdminCreate(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str = "super_admin"
    department_name: str | None = None


class AdminUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    department_name: str | None = None
    active: bool | None = None


class AdminLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    admin: AdminRead


class KpiSummary(BaseModel):
    total_users: int
    total_drivers: int
    total_rides: int
    completed_rides: int
    cancelled_rides: int
    total_revenue_fcfa: int
    total_commission_fcfa: int
    pending_withdrawals: int
    pending_driver_approvals: int

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import USER_ROLE_DRIVER, USER_ROLE_PASSENGER


class UserBase(BaseModel):
    phone: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    role: str = USER_ROLE_PASSENGER
    city: str | None = None
    slang_mode: bool = True


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    city: str | None = None
    slang_mode: bool | None = None
    role: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_phone_verified: bool
    is_active: bool
    is_admin: bool
    admin_role: str | None = None
    created_at: datetime

    @property
    def is_driver(self) -> bool:
        return self.role == USER_ROLE_DRIVER


class UserRegisterRequest(BaseModel):
    phone: str
    name: str | None = None
    role: str = USER_ROLE_PASSENGER
    city: str | None = None

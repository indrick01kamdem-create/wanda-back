import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ADMIN_SUPER = "super_admin"
ADMIN_ACCOUNTING = "accounting"
ADMIN_PUBLICITY = "publicity"
ADMIN_FORENSIC = "forensic"


class AdminAccount(Base):
    """Administrator roster. Doc id == user id (users.is_admin must be true)."""

    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default=ADMIN_SUPER, nullable=False)
    department_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

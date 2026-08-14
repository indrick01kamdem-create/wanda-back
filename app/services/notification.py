from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.settings import Notification
from app.models.user import USER_ROLE_DRIVER, USER_ROLE_PASSENGER, User

logger = logging.getLogger(__name__)

TARGET_ALL = "all"


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, data: dict) -> Notification:
        notification = Notification(**data)
        self._db.add(notification)
        await self._db.commit()
        await self._db.refresh(notification)
        return notification

    async def list_for_user(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        target = user.role
        stmt = (
            select(Notification)
            .where(Notification.target.in_([TARGET_ALL, target]))
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, notification_id: str, user_id: str) -> Notification:
        notification = await self._db.get(Notification, notification_id)
        if notification is None:
            raise NotFoundException("Notification introuvable")
        read_by = list(notification.read_by or [])
        if user_id not in read_by:
            read_by.append(user_id)
        notification.read_by = read_by
        await self._db.commit()
        await self._db.refresh(notification)
        return notification

    async def delete(self, notification_id: str) -> None:
        notification = await self._db.get(Notification, notification_id)
        if notification is None:
            raise NotFoundException("Notification introuvable")
        await self._db.delete(notification)
        await self._db.commit()

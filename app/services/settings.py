from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import NotificationSchedule, SystemSettings
from app.schemas.settings import NotificationScheduleUpdate, SystemSettingsUpdate


class SettingsService:
    """CRUD des réglages système (pricing + promo + schedule notifications)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self) -> SystemSettings:
        row = (
            await self._db.execute(select(SystemSettings).limit(1))
        ).scalar_one_or_none()
        if row is None:
            row = SystemSettings()
            self._db.add(row)
            await self._db.commit()
            await self._db.refresh(row)
        return row

    async def update(self, data: SystemSettingsUpdate) -> SystemSettings:
        row = await self.get()
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(row, field, value)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def get_schedule(self) -> NotificationSchedule:
        row = (
            await self._db.execute(select(NotificationSchedule).limit(1))
        ).scalar_one_or_none()
        if row is None:
            row = NotificationSchedule(
                enabled=True,
                times_per_day=3,
                times_list=["08:00", "12:30", "18:00"],
                language="fr",
                templates={
                    "passengerTemplates": [
                        {"title": "Wanda vous manque ?", "message": "Votre prochain trajet avec Wanda ne coûte qu'un appel.", "includeRouteFare": False}
                    ],
                    "driverTemplates": [
                        {"title": "Nouvelle demande", "message": "Des courses arrivent à proximité, restez connecté.", "includeRouteFare": False}
                    ],
                },
            )
            self._db.add(row)
            await self._db.commit()
            await self._db.refresh(row)
        return row

    async def update_schedule(self, data: NotificationScheduleUpdate) -> NotificationSchedule:
        row = await self.get_schedule()
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(row, field, value)
        await self._db.commit()
        await self._db.refresh(row)
        return row

"""
Tâche planifiée : notifications quotidiennes selon NotificationSchedule.
Exécutée par APScheduler (voir app/tasks/scheduler.py).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.settings import Notification, NotificationSchedule

logger = logging.getLogger(__name__)


async def _send_daily_notifications() -> None:
    """Crée une Notification pour chaque cible configurée (idempotent par jour)."""
    async with AsyncSessionLocal() as db:
        schedule = (
            await db.execute(select(NotificationSchedule).limit(1))
        ).scalar_one_or_none()
        if schedule is None or not schedule.enabled:
            logger.info("Notifications planifiées désactivées")
            return

        templates = schedule.templates or {}
        target_groups = {
            "passenger": templates.get("passengerTemplates") or [],
            "driver": templates.get("driverTemplates") or [],
        }

        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        for target, tpl_list in target_groups.items():
            if not tpl_list:
                continue
            tpl = tpl_list[0]
            created_today = (
                await db.execute(
                    select(func.count(Notification.id)).where(
                        Notification.title == tpl.get("title", ""),
                        Notification.created_at >= start_of_day,
                    )
                )
            ).scalar_one()
            if created_today:
                continue
            db.add(
                Notification(
                    target=target,
                    title=tpl.get("title", "Wanda"),
                    message=tpl.get("message", ""),
                    type="promo",
                    language=schedule.language,
                )
            )

        await db.commit()
        logger.info("Notifications quotidiennes envoyées")

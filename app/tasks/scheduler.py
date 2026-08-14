"""
Scheduler APScheduler — démarrage au boot de l'API.
Tâche : notifications quotidiennes (créées côté base, aucun FCM requis).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Africa/Douala")


def start_scheduler() -> None:
    """Démarre le scheduler avec les tâches planifiées."""
    from app.tasks.notifications import _send_daily_notifications

    # Toutes les 2h entre 08:00 et 22:00, plus un check au boot.
    scheduler.add_job(
        _send_daily_notifications,
        CronTrigger(hour="8-22/2", minute="0"),
        id="daily_notifications",
        max_instances=1,
        coalesce=True,
    )

    if settings.app_env != "test":
        scheduler.start()
        logger.info("Scheduler APScheduler démarré")

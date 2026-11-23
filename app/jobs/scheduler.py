from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.jobs.digest_job import run_daily

logger = logging.getLogger(__name__)


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    timezone = ZoneInfo(settings.default_timezone)
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(
        run_daily,
        CronTrigger(hour=settings.digest_hour, minute=0, timezone=timezone),
        id="daily_digest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "scheduler started daily digest hour=%s tz=%s",
        settings.digest_hour,
        settings.default_timezone,
    )
    return scheduler

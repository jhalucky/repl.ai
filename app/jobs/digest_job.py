from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import TextIO

from app.alerts.digest import founder_alert_destination, send_founder_digest, smtp_ready
from app.config import get_settings
from app.db.session import SessionLocal
from app.jobs.sync_job import run_scheduled_sync
from app.providers.factory import LLMConfigError

logger = logging.getLogger(__name__)


def run_founder_digest(*, skip_sync: bool = False, hours: int | None = None) -> tuple[int, str]:
    newer_than = f"{hours}h" if hours else None
    if not skip_sync:
        run_scheduled_sync(newer_than=newer_than, use_history=hours is None)
    settings = get_settings()
    since = datetime.now(UTC) - timedelta(hours=hours) if hours else None
    session = SessionLocal()
    try:
        count, status = send_founder_digest(session, settings=settings, since=since)
        session.commit()
        return count, status
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_daily() -> None:
    try:
        run_scheduled_sync()
    except Exception:
        logger.exception("daily sync failed")
        raise
    settings = get_settings()
    dest = founder_alert_destination(settings)
    if not dest:
        logger.warning("daily digest skipped: no founder alert email")
        return
    if not smtp_ready(settings, to_email=dest):
        logger.warning("daily digest skipped: SMTP is not configured")
        return
    try:
        count, status = run_founder_digest(skip_sync=True)
        logger.info("daily digest %s count=%s", status, count)
    except Exception:
        logger.exception("daily digest failed")


def main(argv: list[str] | None = None, out: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync connected Gmail accounts and email the founder digest."
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Send the report from the database without fetching Gmail first",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=None,
        help="Only sync and report mail from the last N hours (for a test run)",
    )
    args = parser.parse_args(argv)
    try:
        count, status = run_founder_digest(skip_sync=args.skip_sync, hours=args.hours)
    except LLMConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2
    (out or sys.stdout).write(f"{status}  threads={count}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

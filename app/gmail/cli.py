from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from typing import TextIO

from sqlalchemy import select

from app.db.models import Account
from app.db.session import SessionLocal
from app.gmail.client import GmailClient, ThreadView
from app.gmail.errors import NeedsReconnectError


def format_waiting(view: ThreadView, *, now: datetime | None = None) -> str:
    if view.last_message_from_me:
        return "-"
    now = now or datetime.now(UTC)
    at = view.last_message_at
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    delta: timedelta = now - at
    seconds = max(int(delta.total_seconds()), 0)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _truncate(text: str, width: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= width:
        return compact
    return compact[: width - 3] + "..."


def format_table(views: list[ThreadView], *, now: datetime | None = None) -> str:
    header = f"{'DATE':<12} {'LAST SENDER':<32} {'SUBJECT':<44} {'ME':<5} {'WAITING'}"
    lines = [header]
    for view in views:
        date = view.last_message_at.astimezone(UTC).date().isoformat()
        replied = "yes" if view.last_message_from_me else "no"
        lines.append(
            f"{date:<12} {_truncate(view.last_sender, 32):<32} "
            f"{_truncate(view.subject, 44):<44} {replied:<5} "
            f"{format_waiting(view, now=now)}"
        )
    if not views:
        lines.append("(no threads)")
    return "\n".join(lines) + "\n"


def load_gmail_account(session, email: str | None = None) -> Account:
    stmt = select(Account).where(Account.provider == "gmail")
    if email:
        stmt = stmt.where(Account.account_email == email.strip().lower())
    account = session.scalars(stmt.order_by(Account.id)).first()
    if account is None:
        raise SystemExit(
            "No Gmail account connected. Start the API and open /auth/google/start"
        )
    if account.status == "needs_reconnect":
        raise NeedsReconnectError(account.id)
    return account


def run_threads(*, limit: int, email: str | None = None) -> list[ThreadView]:
    session = SessionLocal()
    try:
        account = load_gmail_account(session, email)
        client = GmailClient.from_account(account, session)
        views = client.list_recent_threads(limit=limit, include_body=False)
        session.commit()
        return views
    except NeedsReconnectError:
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv: list[str] | None = None, out: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Gmail helpers (no bodies printed).")
    sub = parser.add_subparsers(dest="command", required=True)
    threads_p = sub.add_parser("threads", help="List recent threads")
    threads_p.add_argument("--limit", type=int, default=20)
    threads_p.add_argument("--email", default=None, help="Gmail address if you have more than one")
    args = parser.parse_args(argv)
    stream = out or sys.stdout
    try:
        if args.command == "threads":
            views = run_threads(limit=args.limit, email=args.email)
            stream.write(format_table(views))
            return 0
    except NeedsReconnectError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

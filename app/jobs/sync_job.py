from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TextIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Account, Classification, SenderStat, Thread
from app.db.session import SessionLocal
from app.gmail.client import GmailClient, ThreadView
from app.gmail.errors import NeedsReconnectError
from app.pipeline.classifier import classify_one
from app.pipeline.thread_state import apply_message_state
from app.providers.base import EmailInput, LLMProvider
from app.providers.factory import LLMConfigError, get_llm_provider

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    account_id: int
    account_email: str
    threads_seen: int = 0
    threads_upserted: int = 0
    classified: int = 0
    skipped: int = 0
    answered: int = 0
    used_history: bool = False
    reconnect: bool = False
    errors: list[str] = field(default_factory=list)


def _truncate(value: str, limit: int) -> str:
    return value[:limit]


def _thread_changed(existing: Thread, view: ThreadView) -> bool:
    return (
        existing.last_message_at != view.last_message_at
        or existing.last_sender != view.last_sender
        or existing.last_message_from_me != view.last_message_from_me
        or existing.subject != view.subject
    )


def _email_input(view: ThreadView) -> EmailInput:
    body = view.body if view.body else view.snippet
    return EmailInput.model_validate(
        {
            "from": view.last_sender,
            "subject": view.subject,
            "body": body or "",
            "headers": view.headers,
        }
    )


def _sender_weight(session: Session, user_id: int, sender: str) -> float:
    stat = session.scalar(
        select(SenderStat).where(SenderStat.user_id == user_id, SenderStat.sender == sender)
    )
    if stat is None:
        return 1.0
    return float(stat.importance_weight)


def _store_classification(
    session: Session,
    thread: Thread,
    *,
    needs_reply: bool | None,
    urgency: int,
    category: str,
    deadline: str | None,
    reason: str,
    summary: str,
    model: str,
) -> None:
    session.add(
        Classification(
            thread_id=thread.id,
            needs_reply=needs_reply,
            urgency=urgency,
            category=category,
            deadline=deadline,
            reason=_truncate(reason, 512),
            summary=_truncate(summary, 200),
            model=_truncate(model, 128),
        )
    )


def _classify_view(
    session: Session,
    account: Account,
    thread: Thread,
    view: ThreadView,
    client: Any,
    provider: LLMProvider | None,
    settings: Settings,
    stats: SyncStats,
) -> None:
    if view.last_message_from_me:
        stats.skipped += 1
        return
    if provider is None:
        stats.skipped += 1
        return
    full = view
    if view.body is None:
        full = client.get_thread(view.thread_id, include_body=True)
    email = _email_input(full)
    weight = _sender_weight(session, account.user_id, view.last_sender)
    skipped, result = classify_one(email, provider, importance_weight=weight)
    if skipped or result is None:
        stats.skipped += 1
        _store_classification(
            session,
            thread,
            needs_reply=False,
            urgency=1,
            category="other",
            deadline=None,
            reason="skipped by rules",
            summary=_truncate(view.subject, 200),
            model="rules_filter",
        )
        return
    stats.classified += 1
    _store_classification(
        session,
        thread,
        needs_reply=result.needs_reply,
        urgency=result.urgency,
        category=result.category,
        deadline=result.deadline,
        reason=result.reason,
        summary=result.summary,
        model=(settings.llm_model or "unknown"),
    )


def upsert_thread(
    session: Session, account: Account, view: ThreadView, now: datetime
) -> tuple[Thread, bool]:
    thread = session.scalar(
        select(Thread).where(
            Thread.account_id == account.id,
            Thread.provider_thread_id == view.thread_id,
        )
    )
    is_new = thread is None
    changed = True
    if thread is None:
        thread = Thread(
            account_id=account.id,
            provider_thread_id=view.thread_id,
            subject=_truncate(view.subject, 998),
            last_sender=_truncate(view.last_sender, 320),
            last_message_at=view.last_message_at,
            last_message_from_me=view.last_message_from_me,
            status="open",
        )
        session.add(thread)
        session.flush()
    else:
        changed = _thread_changed(thread, view)
        thread.subject = _truncate(view.subject, 998)
        thread.last_sender = _truncate(view.last_sender, 320)
        thread.last_message_at = view.last_message_at
        thread.last_message_from_me = view.last_message_from_me
    apply_message_state(thread, last_message_from_me=view.last_message_from_me, now=now)
    session.flush()
    return thread, is_new or changed


def _has_classification(session: Session, thread_id: int) -> bool:
    return (
        session.scalar(
            select(Classification.id).where(Classification.thread_id == thread_id).limit(1)
        )
        is not None
    )


def expire_snoozes(session: Session, account_id: int, now: datetime) -> None:
    rows = session.scalars(
        select(Thread).where(Thread.account_id == account_id, Thread.status == "snoozed")
    )
    for thread in rows:
        apply_message_state(thread, last_message_from_me=thread.last_message_from_me, now=now)


def sync_account(
    session: Session,
    account: Account,
    client: Any,
    provider: LLMProvider | None,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    newer_than: str | None = None,
    use_history: bool = True,
) -> SyncStats:
    settings = settings or get_settings()
    current = now or datetime.now(UTC)
    stats = SyncStats(account_id=account.id, account_email=account.account_email)
    batch = client.fetch_for_sync(
        history_cursor=account.history_cursor,
        days=settings.sync_lookback_days,
        limit=settings.sync_max_threads,
        newer_than=newer_than,
        use_history=use_history,
    )
    stats.used_history = batch.used_history
    stats.threads_seen = len(batch.threads)
    for view in batch.threads:
        thread, changed = upsert_thread(session, account, view, current)
        stats.threads_upserted += 1
        if thread.status == "answered":
            stats.answered += 1
        missing = not view.last_message_from_me and not _has_classification(session, thread.id)
        if changed or missing:
            _classify_view(session, account, thread, view, client, provider, settings, stats)
    expire_snoozes(session, account.id, current)
    if batch.history_id:
        account.history_cursor = batch.history_id
    account.last_synced_at = current
    session.flush()
    logger.info(
        "sync account_id=%s seen=%s classified=%s skipped=%s history=%s",
        account.id,
        stats.threads_seen,
        stats.classified,
        stats.skipped,
        stats.used_history,
    )
    return stats


def sync_all_accounts(
    session: Session,
    *,
    provider: LLMProvider | None = None,
    now: datetime | None = None,
    settings: Settings | None = None,
    client_factory: Any = GmailClient.from_account,
    email: str | None = None,
    newer_than: str | None = None,
    use_history: bool = True,
) -> list[SyncStats]:
    settings = settings or get_settings()
    stmt = select(Account).where(Account.provider == "gmail", Account.status == "active")
    if email:
        stmt = stmt.where(Account.account_email == email.strip().lower())
    accounts = list(session.scalars(stmt.order_by(Account.id)))
    results: list[SyncStats] = []
    for account in accounts:
        try:
            client = client_factory(account, session)
            results.append(
                sync_account(
                    session,
                    account,
                    client,
                    provider,
                    now=now,
                    settings=settings,
                    newer_than=newer_than,
                    use_history=use_history,
                )
            )
        except NeedsReconnectError:
            results.append(
                SyncStats(
                    account_id=account.id,
                    account_email=account.account_email,
                    reconnect=True,
                )
            )
        except Exception:
            logger.exception("sync failed account_id=%s", account.id)
            results.append(
                SyncStats(
                    account_id=account.id,
                    account_email=account.account_email,
                    errors=["sync failed"],
                )
            )
    return results


def run_scheduled_sync(
    *,
    newer_than: str | None = None,
    use_history: bool = True,
) -> None:
    session = SessionLocal()
    try:
        provider: LLMProvider | None
        try:
            provider = get_llm_provider()
        except LLMConfigError:
            logger.warning("sync: LLM not configured; updating thread state only")
            provider = None
        sync_all_accounts(
            session,
            provider=provider,
            newer_than=newer_than,
            use_history=use_history,
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("sync job failed")
        raise
    finally:
        session.close()


def format_stats(results: list[SyncStats]) -> str:
    if not results:
        return "No active Gmail accounts. Connect at /auth/google/start\n"
    lines = []
    for stats in results:
        extra = ""
        if stats.reconnect:
            extra = " needs_reconnect"
        elif stats.errors:
            extra = " error"
        lines.append(
            f"{stats.account_email}  threads={stats.threads_upserted} "
            f"classified={stats.classified} skipped={stats.skipped} "
            f"answered={stats.answered} history={stats.used_history}{extra}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, out: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Gmail threads into the database.")
    parser.add_argument("--email", default=None, help="Limit to one connected Gmail address")
    args = parser.parse_args(argv)
    session = SessionLocal()
    try:
        provider: LLMProvider | None
        try:
            provider = get_llm_provider()
        except LLMConfigError as exc:
            print(exc, file=sys.stderr)
            provider = None
        results = sync_all_accounts(session, provider=provider, email=args.email)
        session.commit()
        (out or sys.stdout).write(format_stats(results))
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

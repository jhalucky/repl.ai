from __future__ import annotations

import logging
import smtplib
import ssl
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Account, Alert, Classification, Thread
from app.pipeline.thread_state import hours_waiting

logger = logging.getLogger(__name__)


@dataclass
class DigestItem:
    account_email: str
    subject: str
    last_sender: str
    last_message_at: datetime
    urgency: int
    category: str
    reason: str
    deadline: str | None
    thread_id: int
    needs_reply: bool | None = None


def format_wait(last_message_at: datetime, now: datetime) -> str:
    hours = hours_waiting(last_message_at, now)
    if hours >= 24:
        days = int(hours // 24)
        rem = int(hours % 24)
        return f"{days}d {rem}h"
    if hours >= 1:
        return f"{int(hours)}h"
    return f"{max(int(hours * 60), 0)}m"


def threads_requiring_reply(session: Session) -> list[DigestItem]:
    return [
        item
        for item in classified_inbound_threads(session)
        if item.needs_reply is True
    ]


def classified_inbound_threads(
    session: Session, *, since: datetime | None = None
) -> list[DigestItem]:
    latest = (
        select(Classification.thread_id, func.max(Classification.id).label("id"))
        .group_by(Classification.thread_id)
        .subquery()
    )
    rows = session.execute(
        select(Thread, Classification, Account)
        .join(latest, latest.c.thread_id == Thread.id)
        .join(Classification, Classification.id == latest.c.id)
        .join(Account, Account.id == Thread.account_id)
        .where(
            Thread.status == "open",
            Thread.last_message_from_me.is_(False),
            Classification.needs_reply.is_not(None),
            Account.status == "active",
            Account.provider == "gmail",
            *([Thread.last_message_at >= since] if since is not None else []),
        )
        .order_by(Classification.urgency.desc(), Thread.last_message_at.asc())
    ).all()
    items: list[DigestItem] = []
    for thread, classification, account in rows:
        items.append(
            DigestItem(
                account_email=account.account_email,
                subject=thread.subject or "(no subject)",
                last_sender=thread.last_sender,
                last_message_at=thread.last_message_at,
                urgency=classification.urgency,
                category=classification.category,
                reason=classification.reason,
                deadline=classification.deadline,
                thread_id=thread.id,
                needs_reply=classification.needs_reply,
            )
        )
    return items


def _section(title: str, items: list[DigestItem], now: datetime) -> list[str]:
    if not items:
        return [title, "  (none)", ""]
    grouped: dict[str, list[DigestItem]] = defaultdict(list)
    for item in items:
        grouped[item.account_email].append(item)
    lines = [title]
    for mailbox in sorted(grouped):
        lines.append(f"  {mailbox}")
        for item in grouped[mailbox]:
            waited = format_wait(item.last_message_at, now)
            deadline = f"  deadline: {item.deadline}" if item.deadline else ""
            lines.append(
                f"    • {item.last_sender} — {item.subject}  "
                f"(u{item.urgency} {item.category}, waiting {waited})"
            )
            if item.reason:
                lines.append(f"      {item.reason}{deadline}")
        lines.append("")
    return lines


def format_digest(items: list[DigestItem], *, now: datetime | None = None) -> tuple[str, str]:
    current = now or datetime.now(UTC)
    needs = [item for item in items if item.needs_reply is True]
    skip = [item for item in items if item.needs_reply is not True]
    inboxes = len({item.account_email for item in items})
    if not items:
        return (
            "Inbox-guard: no classified inbound mail",
            "No open inbound threads to report across connected inboxes.\n",
        )
    subject = (
        f"Inbox-guard: {len(needs)} need a reply, {len(skip)} do not "
        f"({inboxes} inbox(es))"
    )
    lines = [
        "Classified report (no email bodies).",
        f"Needs a reply: {len(needs)}",
        f"No reply needed: {len(skip)}",
        "",
    ]
    lines.extend(_section("NEEDS A REPLY", needs, current))
    lines.extend(_section("NO REPLY NEEDED", skip, current))
    return subject, "\n".join(lines).rstrip() + "\n"


def founder_alert_destination(settings: Settings | None = None) -> str:
    """Prefer the email saved on /register; fall back to FOUNDER_ALERT_EMAIL."""
    settings = settings or get_settings()
    try:
        from app.registry import get_row

        row = get_row(plan="founder")
        if row is not None and row.alert_email.strip():
            return row.alert_email.strip()
    except Exception:
        logger.warning("could not read founder alert email from registry")
    return settings.founder_alert_email.strip()


def smtp_missing(
    settings: Settings | None = None, *, to_email: str | None = None
) -> list[str]:
    settings = settings or get_settings()
    missing: list[str] = []
    dest = (to_email or "").strip() or settings.founder_alert_email.strip()
    if not dest:
        missing.append("founder alert email")
    if not settings.smtp_host.strip():
        missing.append("SMTP_HOST")
    if not (settings.smtp_from.strip() or settings.smtp_user.strip()):
        missing.append("SMTP_FROM or SMTP_USER")
    if settings.smtp_user.strip() and not settings.smtp_password.strip():
        missing.append("SMTP_PASSWORD")
    return missing


def smtp_ready(
    settings: Settings | None = None, *, to_email: str | None = None
) -> bool:
    return not smtp_missing(settings, to_email=to_email)


def send_email(subject: str, body: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    dest = founder_alert_destination(settings)
    missing = smtp_missing(settings, to_email=dest)
    if missing:
        raise RuntimeError(
            "Save an alert email on /register, then set SMTP in .env: " + ", ".join(missing)
        )
    sender = settings.smtp_from.strip() or settings.smtp_user.strip()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = dest
    message.set_content(body)
    password = settings.smtp_password.replace(" ", "")
    last_error: Exception | None = None
    for port, use_ssl in _smtp_attempts(settings):
        try:
            _smtp_send(
                message,
                host=settings.smtp_host,
                port=port,
                user=settings.smtp_user,
                password=password,
                use_ssl=use_ssl,
                starttls=settings.smtp_starttls and not use_ssl,
            )
            return
        except Exception as exc:
            last_error = exc
            logger.warning("smtp send failed port=%s: %s", port, type(exc).__name__)
    if last_error is not None:
        raise RuntimeError(_smtp_user_message(last_error)) from last_error


def _smtp_attempts(settings: Settings) -> list[tuple[int, bool]]:
    if settings.smtp_port == 465:
        return [(465, True), (587, False)]
    return [(settings.smtp_port or 587, False), (465, True)]


def _smtp_user_message(exc: Exception) -> str:
    text = str(exc).lower()
    if "authentication" in text or "username and password" in text or "535" in text:
        return (
            "Gmail rejected SMTP login. Recreate an App Password on the "
            "FOUNDER_ALERT_EMAIL account, paste SMTP_PASSWORD, save .env, restart the API."
        )
    if "unexpectedly closed" in text or "disconnected" in text:
        return (
            "Gmail closed the SMTP connection. Recreate the App Password for "
            f"{get_settings().smtp_user or 'SMTP_USER'}, save .env, and retry."
        )
    return str(exc)[:180]


def _smtp_send(
    message: EmailMessage,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_ssl: bool,
    starttls: bool,
) -> None:
    context = ssl.create_default_context()
    smtp: smtplib.SMTP
    if use_ssl:
        smtp = smtplib.SMTP_SSL(host, port, timeout=30, context=context)
    else:
        smtp = smtplib.SMTP(host, port, timeout=30)
    try:
        smtp.ehlo()
        if starttls:
            smtp.starttls(context=context)
            smtp.ehlo()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)
    finally:
        try:
            smtp.quit()
        except smtplib.SMTPServerDisconnected:
            pass


def record_digest_alerts(session: Session, items: list[DigestItem]) -> None:
    for item in items:
        session.add(Alert(thread_id=item.thread_id, channel="telegram", kind="digest"))


def send_founder_digest(
    session: Session,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    mailer: Any | None = None,
    since: datetime | None = None,
) -> tuple[int, str]:
    settings = settings or get_settings()
    items = classified_inbound_threads(session, since=since)
    subject, body = format_digest(items, now=now)
    dest = founder_alert_destination(settings)
    if not dest:
        logger.warning("digest skipped: no founder alert email")
        return len(items), "skipped: no alert email"
    settings = settings.model_copy(update={"founder_alert_email": dest})
    deliver = mailer or send_email
    try:
        deliver(subject, body, settings)
    except Exception:
        logger.warning("digest email failed count=%s", len(items))
        raise
    record_digest_alerts(session, [item for item in items if item.needs_reply is True])
    logger.info("digest sent count=%s", len(items))
    return len(items), "sent"

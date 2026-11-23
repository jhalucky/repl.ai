from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings, get_settings
from app.db.models import Classification, Thread

PROTECTED_STATUSES = frozenset({"ignored", "done"})


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def next_status(
    current: str,
    *,
    last_message_from_me: bool,
    snoozed_until: datetime | None,
    now: datetime,
) -> str:
    if current in PROTECTED_STATUSES:
        return current
    if last_message_from_me:
        return "answered"
    if current == "snoozed" and snoozed_until is not None and _aware(snoozed_until) > now:
        return "snoozed"
    return "open"


def apply_message_state(thread: Thread, *, last_message_from_me: bool, now: datetime) -> str:
    thread.status = next_status(
        thread.status,
        last_message_from_me=last_message_from_me,
        snoozed_until=thread.snoozed_until,
        now=now,
    )
    if thread.status != "snoozed":
        thread.snoozed_until = None
    return thread.status


def wait_threshold_hours(urgency: int, settings: Settings | None = None) -> float | None:
    settings = settings or get_settings()
    mapping: dict[int, float | None] = {
        5: float(settings.urgency_5_hours),
        4: float(settings.urgency_4_hours),
        3: float(settings.urgency_3_hours),
        2: float(settings.urgency_2_hours),
        1: None,
    }
    return mapping.get(urgency)


def hours_waiting(last_message_at: datetime, now: datetime) -> float:
    delta = now - _aware(last_message_at)
    return max(delta.total_seconds(), 0.0) / 3600.0


def needs_attention(
    thread: Thread,
    classification: Classification | None,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> bool:
    settings = settings or get_settings()
    current = now or datetime.now(UTC)
    if thread.status != "open" or thread.last_message_from_me:
        return False
    if classification is None or classification.needs_reply is not True:
        return False
    threshold = wait_threshold_hours(classification.urgency, settings)
    if threshold is None:
        return False
    return hours_waiting(thread.last_message_at, current) >= threshold

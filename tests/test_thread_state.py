from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.db.models import Classification, Thread
from app.pipeline.thread_state import apply_message_state, needs_attention, next_status

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
SETTINGS = Settings(
    token_encryption_key="x",
    google_client_id="id",
    google_client_secret="secret",
)


def _thread(**kwargs: object) -> Thread:
    values: dict = {
        "account_id": 1,
        "provider_thread_id": "t1",
        "subject": "Hello",
        "last_sender": "ada@x.com",
        "last_message_at": NOW - timedelta(hours=2),
        "last_message_from_me": False,
        "status": "open",
    }
    values.update(kwargs)
    return Thread(**values)


def _classification(**kwargs: object) -> Classification:
    values: dict = {
        "thread_id": 1,
        "needs_reply": True,
        "urgency": 5,
        "category": "lead",
        "reason": "question",
        "summary": "question",
        "model": "fake",
    }
    values.update(kwargs)
    return Classification(**values)


def test_next_status_answered_when_last_from_me() -> None:
    assert (
        next_status("open", last_message_from_me=True, snoozed_until=None, now=NOW)
        == "answered"
    )


def test_next_status_reopens_answered_when_they_reply() -> None:
    assert (
        next_status("answered", last_message_from_me=False, snoozed_until=None, now=NOW)
        == "open"
    )


def test_next_status_keeps_ignored_and_done() -> None:
    assert (
        next_status("ignored", last_message_from_me=False, snoozed_until=None, now=NOW)
        == "ignored"
    )
    assert next_status("done", last_message_from_me=True, snoozed_until=None, now=NOW) == "done"


def test_next_status_keeps_active_snooze() -> None:
    until = NOW + timedelta(hours=4)
    assert (
        next_status("snoozed", last_message_from_me=False, snoozed_until=until, now=NOW)
        == "snoozed"
    )


def test_next_status_expires_snooze() -> None:
    until = NOW - timedelta(minutes=1)
    assert (
        next_status("snoozed", last_message_from_me=False, snoozed_until=until, now=NOW)
        == "open"
    )


def test_apply_message_state_clears_snooze_when_answered() -> None:
    thread = _thread(status="snoozed", snoozed_until=NOW + timedelta(hours=1))
    apply_message_state(thread, last_message_from_me=True, now=NOW)
    assert thread.status == "answered"
    assert thread.snoozed_until is None


def test_needs_attention_urgency_thresholds() -> None:
    clf = _classification(urgency=5)
    thread = _thread(last_message_at=NOW - timedelta(hours=1))
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is True
    thread.last_message_at = NOW - timedelta(minutes=30)
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is False

    clf.urgency = 4
    thread.last_message_at = NOW - timedelta(hours=2)
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is True
    thread.last_message_at = NOW - timedelta(hours=1)
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is False

    clf.urgency = 3
    thread.last_message_at = NOW - timedelta(hours=24)
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is True

    clf.urgency = 2
    thread.last_message_at = NOW - timedelta(hours=48)
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is True

    clf.urgency = 1
    thread.last_message_at = NOW - timedelta(days=10)
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is False


def test_needs_attention_requires_open_needs_reply_not_from_me() -> None:
    clf = _classification()
    thread = _thread()
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is True

    thread.status = "answered"
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is False

    thread.status = "open"
    thread.last_message_from_me = True
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is False

    thread.last_message_from_me = False
    clf.needs_reply = False
    assert needs_attention(thread, clf, now=NOW, settings=SETTINGS) is False
    assert needs_attention(thread, None, now=NOW, settings=SETTINGS) is False

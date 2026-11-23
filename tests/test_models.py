from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Account, Classification, SenderStat, Thread, User


def test_user_default_timezone(db_session: Session) -> None:
    user = User(email="founder@example.com")
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)

    assert user.timezone == "Asia/Kolkata"
    assert user.telegram_chat_id is None
    assert user.created_at is not None


def test_user_email_unique(db_session: Session) -> None:
    db_session.add(User(email="dup@example.com"))
    db_session.flush()
    db_session.add(User(email="dup@example.com"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_account_default_status_active(db_session: Session) -> None:
    user = User(email="status-acc@example.com")
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        account_email="me@example.com",
        encrypted_refresh_token="encrypted-placeholder",
    )
    db_session.add(account)
    db_session.flush()
    db_session.refresh(account)
    assert account.status == "active"


def test_thread_unique_per_account(db_session: Session) -> None:
    user = User(email="owner@example.com")
    db_session.add(user)
    db_session.flush()

    account = Account(
        user_id=user.id,
        account_email="me@example.com",
        encrypted_refresh_token="encrypted-placeholder",
    )
    db_session.add(account)
    db_session.flush()

    now = datetime.now(UTC)
    db_session.add(
        Thread(
            account_id=account.id,
            provider_thread_id="thread-1",
            subject="Hello",
            last_sender="lead@example.com",
            last_message_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        Thread(
            account_id=account.id,
            provider_thread_id="thread-1",
            subject="Hello again",
            last_sender="lead@example.com",
            last_message_at=now,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_thread_default_status_open(db_session: Session) -> None:
    user = User(email="status@example.com")
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        account_email="me@example.com",
        encrypted_refresh_token="encrypted-placeholder",
    )
    db_session.add(account)
    db_session.flush()

    thread = Thread(
        account_id=account.id,
        provider_thread_id="thread-open",
        last_message_at=datetime.now(UTC),
    )
    db_session.add(thread)
    db_session.flush()
    db_session.refresh(thread)

    assert thread.status == "open"
    assert thread.last_message_from_me is False


def test_classification_urgency_bounds(db_session: Session) -> None:
    user = User(email="urgency@example.com")
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        account_email="me@example.com",
        encrypted_refresh_token="encrypted-placeholder",
    )
    db_session.add(account)
    db_session.flush()
    thread = Thread(
        account_id=account.id,
        provider_thread_id="thread-urg",
        last_message_at=datetime.now(UTC),
    )
    db_session.add(thread)
    db_session.flush()

    db_session.add(
        Classification(
            thread_id=thread.id,
            needs_reply=True,
            urgency=0,
            category="lead",
            reason="out of range",
            summary="bad urgency",
            model="test",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_sender_stats_default_weight(db_session: Session) -> None:
    user = User(email="stats@example.com")
    db_session.add(user)
    db_session.flush()

    stat = SenderStat(user_id=user.id, sender="lead@example.com")
    db_session.add(stat)
    db_session.flush()
    db_session.refresh(stat)

    assert stat.importance_weight == 1.0
    assert stat.replies_sent == 0
    assert stat.last_reply_at is None

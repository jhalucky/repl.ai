from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.alerts.digest import (
    DigestItem,
    classified_inbound_threads,
    format_digest,
    send_founder_digest,
    threads_requiring_reply,
)
from app.db.models import Account, Classification, Thread, User
from app.gmail.crypto import encrypt_token
from app.registry import registry_path


@pytest.fixture(autouse=True)
def _fresh_registry() -> None:
    path = registry_path()
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _item(**kwargs: object) -> DigestItem:
    values: dict = {
        "account_email": "ops@example.com",
        "subject": "Pricing?",
        "last_sender": "ada@x.com",
        "last_message_at": NOW - timedelta(hours=3),
        "urgency": 4,
        "category": "lead",
        "reason": "Asked for a quote",
        "deadline": None,
        "thread_id": 1,
        "needs_reply": True,
    }
    values.update(kwargs)
    return DigestItem(**values)


def test_format_digest_splits_reply_and_skip() -> None:
    subject, body = format_digest(
        [
            _item(subject="Need a call", needs_reply=True),
            _item(
                account_email="org@example.com",
                subject="FYI newsletter",
                last_sender="noreply@x.com",
                needs_reply=False,
                urgency=1,
                category="other",
                reason="Notification",
                thread_id=2,
            ),
        ],
        now=NOW,
    )
    assert "1 need a reply" in subject
    assert "NEEDS A REPLY" in body
    assert "Need a call" in body
    assert "NO REPLY NEEDED" in body
    assert "FYI newsletter" in body
    assert "SECRET" not in body


def test_query_includes_all_classified_inbound(db_session: Session) -> None:
    user = User(email="ops@example.com")
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        account_email="ops@example.com",
        encrypted_refresh_token=encrypt_token("refresh"),
        status="active",
    )
    db_session.add(account)
    db_session.flush()
    need = Thread(
        account_id=account.id,
        provider_thread_id="t-need",
        subject="Offer?",
        last_sender="lead@x.com",
        last_message_at=NOW - timedelta(hours=5),
        last_message_from_me=False,
        status="open",
    )
    skip = Thread(
        account_id=account.id,
        provider_thread_id="t-skip",
        subject="Thanks",
        last_sender="ada@x.com",
        last_message_at=NOW - timedelta(minutes=30),
        last_message_from_me=False,
        status="open",
    )
    mine = Thread(
        account_id=account.id,
        provider_thread_id="t-me",
        subject="Re: Offer",
        last_sender="ops@example.com",
        last_message_at=NOW,
        last_message_from_me=True,
        status="answered",
    )
    db_session.add_all([need, skip, mine])
    db_session.flush()
    db_session.add_all(
        [
            Classification(
                thread_id=need.id,
                needs_reply=True,
                urgency=4,
                category="lead",
                reason="offer",
                summary="offer",
                model="fake",
            ),
            Classification(
                thread_id=skip.id,
                needs_reply=False,
                urgency=1,
                category="other",
                reason="thanks",
                summary="thanks",
                model="fake",
            ),
        ]
    )
    db_session.flush()

    all_items = classified_inbound_threads(db_session)
    assert {item.subject for item in all_items} == {"Offer?", "Thanks"}
    assert [item.subject for item in threads_requiring_reply(db_session)] == ["Offer?"]
    recent = classified_inbound_threads(db_session, since=NOW - timedelta(hours=1))
    assert {item.subject for item in recent} == {"Thanks"}


def test_send_digest_uses_founder_address(db_session: Session, monkeypatch) -> None:
    from app.config import Settings

    settings = Settings(
        founder_alert_email="boss@example.com",
        smtp_host="smtp.example.com",
        smtp_from="alerts@example.com",
        token_encryption_key="x",
        google_client_id="id",
        google_client_secret="secret",
    )
    sent: list[tuple[str, str]] = []

    def fake_mail(subject: str, body: str, _settings=None) -> None:
        sent.append((subject, body))

    count, status = send_founder_digest(
        db_session, now=NOW, settings=settings, mailer=fake_mail
    )
    assert status == "sent"
    assert count == 0
    assert sent
    assert "no classified inbound" in sent[0][0].lower()


def test_send_digest_prefers_registry_alert_email(db_session: Session) -> None:
    from app.config import Settings
    from app.registry import RegistryRow, upsert_row

    upsert_row(
        RegistryRow(id="founder", plan="founder", alert_email="from-sheet@example.com")
    )
    settings = Settings(
        founder_alert_email="from-env@example.com",
        smtp_host="smtp.example.com",
        smtp_from="alerts@example.com",
        token_encryption_key="x",
        google_client_id="id",
        google_client_secret="secret",
    )
    captured: list[str] = []

    def fake_mail(subject: str, body: str, mail_settings=None) -> None:
        captured.append(mail_settings.founder_alert_email)

    _, status = send_founder_digest(
        db_session, now=NOW, settings=settings, mailer=fake_mail
    )
    assert status == "sent"
    assert captured == ["from-sheet@example.com"]

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Account, Classification, Thread, User
from app.gmail.client import SyncBatch, ThreadView
from app.gmail.crypto import encrypt_token
from app.jobs.sync_job import sync_account, sync_all_accounts
from app.pipeline.thread_state import needs_attention
from tests.fakes import FakeProvider

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _view(
    thread_id: str = "t1",
    *,
    sender: str = "ada@x.com",
    subject: str = "Pricing?",
    from_me: bool = False,
    at: datetime | None = None,
    snippet: str = "Can you send pricing please",
    body: str | None = "Can you send pricing please",
    headers: dict[str, str] | None = None,
) -> ThreadView:
    return ThreadView(
        thread_id=thread_id,
        subject=subject,
        last_sender=sender,
        last_message_at=at or NOW - timedelta(hours=3),
        last_message_from_me=from_me,
        snippet=snippet,
        headers=headers or {"From": sender, "Subject": subject},
        body=body,
    )


@dataclass
class FakeGmailClient:
    views: list[ThreadView]
    history_id: str = "100"
    fetch_calls: int = 0
    get_calls: list[tuple[str, bool]] = field(default_factory=list)

    def fetch_for_sync(
        self,
        *,
        history_cursor: str | None,
        days: int,
        limit: int,
        newer_than: str | None = None,
        use_history: bool = True,
    ) -> SyncBatch:
        self.fetch_calls += 1
        metadata = [
            ThreadView(
                thread_id=view.thread_id,
                subject=view.subject,
                last_sender=view.last_sender,
                last_message_at=view.last_message_at,
                last_message_from_me=view.last_message_from_me,
                snippet=view.snippet,
                headers=view.headers,
                body=None,
            )
            for view in self.views
        ]
        return SyncBatch(
            threads=metadata,
            history_id=self.history_id,
            used_history=bool(history_cursor),
        )

    def get_thread(self, thread_id: str, *, include_body: bool = False) -> ThreadView:
        self.get_calls.append((thread_id, include_body))
        for view in self.views:
            if view.thread_id == thread_id:
                return ThreadView(
                    thread_id=view.thread_id,
                    subject=view.subject,
                    last_sender=view.last_sender,
                    last_message_at=view.last_message_at,
                    last_message_from_me=view.last_message_from_me,
                    snippet=view.snippet,
                    headers=view.headers,
                    body=view.body if include_body else None,
                )
        raise KeyError(thread_id)


def _account(session: Session, email: str = "me@example.com") -> Account:
    user = User(email=email)
    session.add(user)
    session.flush()
    account = Account(
        user_id=user.id,
        account_email=email,
        encrypted_refresh_token=encrypt_token("refresh-token"),
        status="active",
    )
    session.add(account)
    session.flush()
    return account


def test_sync_twice_is_idempotent(db_session: Session) -> None:
    account = _account(db_session)
    client = FakeGmailClient(
        [
            _view("t-in", sender="ada@x.com", subject="Pricing?"),
            _view("t-me", sender="me@example.com", subject="Re: Hello", from_me=True),
        ]
    )
    provider = FakeProvider()
    first = sync_account(db_session, account, client, provider, now=NOW)
    second = sync_account(db_session, account, client, provider, now=NOW)

    assert first.threads_upserted == 2
    assert second.threads_upserted == 2
    assert db_session.scalar(select(func.count()).select_from(Thread)) == 2
    assert db_session.scalar(select(func.count()).select_from(Classification)) == 1
    assert len(provider.calls) == 1
    me = db_session.scalar(select(Thread).where(Thread.provider_thread_id == "t-me"))
    assert me is not None
    assert me.status == "answered"
    assert account.history_cursor == "100"
    assert account.last_synced_at == NOW


def test_replied_thread_flips_to_answered(db_session: Session) -> None:
    account = _account(db_session)
    incoming = _view("t1", sender="ada@x.com", subject="Need intro")
    client = FakeGmailClient([incoming])
    provider = FakeProvider()
    sync_account(db_session, account, client, provider, now=NOW)
    thread = db_session.scalar(select(Thread).where(Thread.provider_thread_id == "t1"))
    assert thread is not None
    assert thread.status == "open"
    assert thread.last_message_from_me is False

    incoming.last_message_from_me = True
    incoming.last_sender = "me@example.com"
    incoming.last_message_at = NOW
    incoming.subject = "Re: Need intro"
    sync_account(db_session, account, client, provider, now=NOW)

    db_session.refresh(thread)
    assert thread.status == "answered"
    assert thread.last_message_from_me is True
    assert db_session.scalar(select(func.count()).select_from(Thread)) == 1
    assert db_session.scalar(select(func.count()).select_from(Classification)) == 1


def test_classifies_threads_that_had_no_llm(db_session: Session) -> None:
    account = _account(db_session)
    client = FakeGmailClient([_view()])
    sync_account(db_session, account, client, None, now=NOW)
    assert db_session.scalar(select(func.count()).select_from(Classification)) == 0
    provider = FakeProvider()
    sync_account(db_session, account, client, provider, now=NOW)
    assert len(provider.calls) == 1
    assert db_session.scalar(select(func.count()).select_from(Classification)) == 1
    sync_account(db_session, account, client, provider, now=NOW)
    assert len(provider.calls) == 1


def test_unchanged_thread_is_not_reclassified(db_session: Session) -> None:
    account = _account(db_session)
    client = FakeGmailClient([_view()])
    provider = FakeProvider()
    sync_account(db_session, account, client, provider, now=NOW)
    sync_account(db_session, account, client, provider, now=NOW + timedelta(minutes=5))
    assert len(provider.calls) == 1
    assert [call[1] for call in client.get_calls] == [True]


def test_rules_skip_stores_needs_reply_false(db_session: Session) -> None:
    account = _account(db_session)
    view = _view(
        sender="noreply@news.example",
        subject="Weekly dump",
        snippet="unsubscribe",
        body="unsubscribe",
        headers={"From": "noreply@news.example", "List-Unsubscribe": "<https://x>"},
    )
    client = FakeGmailClient([view])
    provider = FakeProvider()
    sync_account(db_session, account, client, provider, now=NOW)
    assert provider.calls == []
    row = db_session.scalar(select(Classification))
    assert row is not None
    assert row.needs_reply is False
    assert row.model == "rules_filter"


def test_needs_reconnect_account_is_skipped(db_session: Session) -> None:
    account = _account(db_session)
    account.status = "needs_reconnect"
    db_session.flush()
    called = []

    def factory(acc: Account, session: Session) -> FakeGmailClient:
        called.append(acc.id)
        return FakeGmailClient([])

    results = sync_all_accounts(
        db_session, provider=FakeProvider(), client_factory=factory, now=NOW
    )
    assert results == []
    assert called == []


def test_synced_open_thread_needs_attention(db_session: Session) -> None:
    account = _account(db_session)
    client = FakeGmailClient([_view(subject="Offer?", body="please confirm the offer")])
    provider = FakeProvider()
    sync_account(db_session, account, client, provider, now=NOW)
    thread = db_session.scalar(select(Thread))
    classification = db_session.scalar(select(Classification))
    assert thread is not None
    assert needs_attention(thread, classification, now=NOW) is True

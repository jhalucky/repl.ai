from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.db.models import Account, User
from app.gmail.client import GmailClient, refresh_credentials
from app.gmail.crypto import encrypt_token
from app.gmail.errors import HistoryExpiredError, NeedsReconnectError
from app.gmail.parser import METADATA_HEADERS
from tests.test_gmail_parser import _message


class FakeRequest:
    def __init__(self, result=None, error=None) -> None:
        self._result = result
        self._error = error
        self.calls = 0
        self.kwargs: dict = {}

    def execute(self):
        self.calls += 1
        if self._error and self.calls == 1:
            raise self._error
        if callable(self._result):
            return self._result()
        return self._result


class FakeThreads:
    def __init__(self, list_req: FakeRequest, get_req: FakeRequest) -> None:
        self._list = list_req
        self._get = get_req
        self.get_kwargs: dict | None = None
        self.get_ids: list[str] = []

    def list(self, **kwargs: object) -> FakeRequest:
        self._list.kwargs = kwargs
        return self._list

    def get(self, **kwargs: object) -> FakeRequest:
        self.get_kwargs = dict(kwargs)
        self._get.kwargs = kwargs
        self.get_ids.append(str(kwargs.get("id") or ""))
        return self._get


class FakeHistory:
    def __init__(self, list_req: FakeRequest) -> None:
        self._list = list_req
        self.list_kwargs: dict | None = None

    def list(self, **kwargs: object) -> FakeRequest:
        self.list_kwargs = dict(kwargs)
        self._list.kwargs = kwargs
        return self._list


class FakeUsers:
    def __init__(
        self,
        threads: FakeThreads,
        history: FakeHistory | None = None,
        profile: FakeRequest | None = None,
    ) -> None:
        self._threads = threads
        self._history = history or FakeHistory(FakeRequest({"history": [], "historyId": "1"}))
        self._profile = profile or FakeRequest(
            {"emailAddress": "me@example.com", "historyId": "1"}
        )

    def threads(self) -> FakeThreads:
        return self._threads

    def history(self) -> FakeHistory:
        return self._history

    def getProfile(self, **kwargs: object) -> FakeRequest:
        return self._profile


class FakeService:
    def __init__(
        self,
        threads: FakeThreads,
        history: FakeHistory | None = None,
        profile: FakeRequest | None = None,
    ) -> None:
        self._users = FakeUsers(threads, history=history, profile=profile)

    def users(self) -> FakeUsers:
        return self._users


def _service(thread: dict, listed: dict | None = None) -> FakeService:
    listed = listed if listed is not None else {"threads": [{"id": "t1"}]}
    return FakeService(FakeThreads(FakeRequest(listed), FakeRequest(thread)))


def _http_error(status: int) -> HttpError:
    class Resp:
        def __init__(self) -> None:
            self.status = status
            self.reason = "error"

        def get(self, name: str, default=None):
            return default

    return HttpError(Resp(), b"{}")


def test_list_recent_threads_metadata_no_body_by_default() -> None:
    thread = {
        "id": "t1",
        "messages": [
            _message(from_header="Ada <ada@x.com>", subject="Pricing?"),
        ],
    }
    list_req = FakeRequest({"threads": [{"id": "t1"}]})
    get_req = FakeRequest(thread)
    service = FakeService(FakeThreads(list_req, get_req))
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)

    views = client.list_recent_threads(limit=20)
    assert list_req.kwargs["q"] == "newer_than:30d"
    assert list_req.kwargs["maxResults"] == 20
    assert service.users().threads().get_kwargs is not None
    assert service.users().threads().get_kwargs["format"] == "metadata"
    assert service.users().threads().get_kwargs["metadataHeaders"] == list(METADATA_HEADERS)
    assert len(views) == 1
    assert views[0].subject == "Pricing?"
    assert views[0].last_sender == "ada@x.com"
    assert views[0].last_message_from_me is False
    assert views[0].body is None


def test_list_recent_threads_newer_than_hours() -> None:
    thread = {
        "id": "t1",
        "messages": [_message(from_header="Ada <ada@x.com>", subject="Now")],
    }
    list_req = FakeRequest({"threads": [{"id": "t1"}]})
    service = FakeService(FakeThreads(list_req, FakeRequest(thread)))
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    client.list_recent_threads(newer_than="1h", limit=20)
    assert list_req.kwargs["q"] == "newer_than:1h"


def test_include_body_uses_full_format() -> None:
    thread = {
        "id": "t1",
        "messages": [_message(from_header="Ada <ada@x.com>", body="SECRET_BODY")],
    }
    service = _service(thread)
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    views = client.list_recent_threads(include_body=True, limit=1)
    assert service.users().threads().get_kwargs["format"] == "full"
    assert "metadataHeaders" not in service.users().threads().get_kwargs
    assert views[0].body == "SECRET_BODY"


def test_last_message_from_me_on_thread() -> None:
    thread = {
        "id": "t1",
        "messages": [
            _message(from_header="Ada <ada@x.com>"),
            _message(from_header="Me <me@example.com>"),
        ],
    }
    service = _service(thread)
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    assert client.list_recent_threads()[0].last_message_from_me is True


def test_retries_on_429() -> None:
    list_req = FakeRequest({"threads": []}, error=_http_error(429))
    service = FakeService(FakeThreads(list_req, FakeRequest({})))
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    assert client.list_recent_threads() == []
    assert list_req.calls == 2


def test_invalid_grant_marks_needs_reconnect(db_session: Session) -> None:
    user = User(email="me@example.com")
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        account_email="me@example.com",
        encrypted_refresh_token=encrypt_token("refresh-token"),
        status="active",
    )
    db_session.add(account)
    db_session.flush()

    creds = MagicMock()
    creds.refresh.side_effect = RefreshError(
        "invalid_grant: Token has been expired or revoked."
    )
    with pytest.raises(NeedsReconnectError):
        refresh_credentials(creds, account, db_session)
    assert account.status == "needs_reconnect"


def test_from_account_invalid_grant(db_session: Session) -> None:
    user = User(email="me@example.com")
    db_session.add(user)
    db_session.flush()
    account = Account(
        user_id=user.id,
        account_email="me@example.com",
        encrypted_refresh_token=encrypt_token("refresh-token"),
        status="active",
    )
    db_session.add(account)
    db_session.flush()
    creds = MagicMock()
    creds.refresh.side_effect = RefreshError("invalid_grant")
    with pytest.raises(NeedsReconnectError):
        GmailClient.from_account(
            account, db_session, credentials=creds, service=MagicMock()
        )
    assert account.status == "needs_reconnect"


def test_non_transient_http_error_is_not_retried() -> None:
    list_req = FakeRequest(error=_http_error(404))
    service = FakeService(FakeThreads(list_req, FakeRequest({})))
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    with pytest.raises(HttpError):
        client.list_recent_threads()
    assert list_req.calls == 1


def test_fetch_for_sync_uses_history_when_cursor_present() -> None:
    thread = {
        "id": "t9",
        "messages": [_message(from_header="Ada <ada@x.com>", subject="Ping")],
    }
    history_req = FakeRequest(
        {
            "historyId": "50",
            "history": [
                {"messages": [{"id": "m1", "threadId": "t9"}]},
                {"messagesAdded": [{"message": {"id": "m2", "threadId": "t9"}}]},
            ],
        }
    )
    list_req = FakeRequest({"threads": [{"id": "should-not-list"}]})
    threads = FakeThreads(list_req, FakeRequest(thread))
    service = FakeService(
        threads,
        history=FakeHistory(history_req),
        profile=FakeRequest({"historyId": "50", "emailAddress": "me@example.com"}),
    )
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    batch = client.fetch_for_sync(history_cursor="40", limit=20)
    assert batch.used_history is True
    assert batch.history_id == "50"
    assert [view.thread_id for view in batch.threads] == ["t9"]
    assert list_req.calls == 0
    assert history_req.kwargs["startHistoryId"] == "40"


def test_fetch_for_sync_falls_back_when_history_expired() -> None:
    thread = {
        "id": "t1",
        "messages": [_message(from_header="Ada <ada@x.com>", subject="Hi")],
    }
    history_req = FakeRequest(error=_http_error(404))
    list_req = FakeRequest({"threads": [{"id": "t1"}]})
    service = FakeService(
        FakeThreads(list_req, FakeRequest(thread)),
        history=FakeHistory(history_req),
        profile=FakeRequest({"historyId": "9", "emailAddress": "me@example.com"}),
    )
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    batch = client.fetch_for_sync(history_cursor="1")
    assert batch.used_history is False
    assert batch.history_id == "9"
    assert [view.thread_id for view in batch.threads] == ["t1"]


def test_list_history_thread_ids_expired() -> None:
    service = FakeService(
        FakeThreads(FakeRequest({"threads": []}), FakeRequest({})),
        history=FakeHistory(FakeRequest(error=_http_error(404))),
    )
    client = GmailClient(account_email="me@example.com", service=service, backoff_seconds=0)
    with pytest.raises(HistoryExpiredError):
        client.list_history_thread_ids("1")


def test_thread_view_waiting_datetime() -> None:
    thread = {
        "id": "t1",
        "messages": [
            _message(from_header="Ada <ada@x.com>", internal_date="1700000000000")
        ],
    }
    client = GmailClient(
        account_email="me@example.com", service=_service(thread), backoff_seconds=0
    )
    view = client.list_recent_threads()[0]
    assert view.last_message_at == datetime.fromtimestamp(1_700_000_000, tz=UTC)

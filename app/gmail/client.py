from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.gmail.crypto import decrypt_token
from app.gmail.errors import HistoryExpiredError, NeedsReconnectError
from app.gmail.oauth import GOOGLE_TOKEN_ENDPOINT, SCOPES
from app.gmail.parser import (
    METADATA_HEADERS,
    decode_body,
    extract_address,
    header_map,
    header_value,
    last_message_from_me,
    message_datetime,
)
from app.providers.http_retry import TransientHttpError, call_with_retry, is_transient_status

logger = logging.getLogger(__name__)


@dataclass
class ThreadView:
    thread_id: str
    subject: str
    last_sender: str
    last_message_at: datetime
    last_message_from_me: bool
    snippet: str
    headers: dict[str, str]
    body: str | None = None


@dataclass
class SyncBatch:
    threads: list[ThreadView]
    history_id: str | None
    used_history: bool


def _http_status(exc: HttpError) -> int:
    status = getattr(exc, "status_code", None)
    if status:
        return int(status)
    resp = getattr(exc, "resp", None)
    return int(getattr(resp, "status", 0) or 0)


def execute_gmail(request: Any, *, backoff_seconds: float = 1.0) -> Any:
    def send() -> Any:
        try:
            return request.execute()
        except HttpError as exc:
            status = _http_status(exc)
            if is_transient_status(status):
                raise TransientHttpError(status) from exc
            if status != 404:
                logger.error("gmail HTTP %s", status)
            raise

    return call_with_retry(send, backoff_seconds=backoff_seconds)


def mark_needs_reconnect(account: Any, session: Session | None) -> None:
    account.status = "needs_reconnect"
    if session is not None:
        session.flush()


def refresh_credentials(
    credentials: Credentials,
    account: Any,
    session: Session | None,
) -> None:
    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        if "invalid_grant" in str(exc).lower():
            logger.warning(
                "gmail refresh invalid_grant account_id=%s", getattr(account, "id", None)
            )
            mark_needs_reconnect(account, session)
            raise NeedsReconnectError(getattr(account, "id", None)) from None
        raise


class GmailClient:
    def __init__(
        self,
        *,
        account_email: str,
        service: Any,
        account: Any | None = None,
        session: Session | None = None,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.account_email = account_email.strip().lower()
        self._service = service
        self._account = account
        self._session = session
        self._backoff_seconds = backoff_seconds

    @classmethod
    def from_account(
        cls,
        account: Any,
        session: Session,
        *,
        credentials: Credentials | None = None,
        service: Any | None = None,
        backoff_seconds: float = 1.0,
    ) -> GmailClient:
        settings = get_settings()
        if credentials is None:
            refresh_token = decrypt_token(account.encrypted_refresh_token)
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=GOOGLE_TOKEN_ENDPOINT,
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                scopes=list(SCOPES),
            )
        refresh_credentials(credentials, account, session)
        if service is None:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        return cls(
            account_email=account.account_email,
            service=service,
            account=account,
            session=session,
            backoff_seconds=backoff_seconds,
        )

    def _execute(self, request: Any) -> Any:
        return execute_gmail(request, backoff_seconds=self._backoff_seconds)

    def list_recent_threads(
        self,
        *,
        days: int = 30,
        limit: int = 20,
        include_body: bool = False,
        newer_than: str | None = None,
    ) -> list[ThreadView]:
        query = f"newer_than:{newer_than}" if newer_than else f"newer_than:{days}d"
        listed = self._execute(
            self._service.users()
            .threads()
            .list(userId="me", q=query, maxResults=limit)
        )
        views: list[ThreadView] = []
        for item in listed.get("threads") or []:
            thread_id = str(item.get("id") or "")
            if not thread_id:
                continue
            views.append(self.get_thread(thread_id, include_body=include_body))
        return views

    def get_thread(self, thread_id: str, *, include_body: bool = False) -> ThreadView:
        kwargs: dict[str, Any] = {
            "userId": "me",
            "id": thread_id,
            "format": "full" if include_body else "metadata",
        }
        if not include_body:
            kwargs["metadataHeaders"] = list(METADATA_HEADERS)
        resource = self._execute(self._service.users().threads().get(**kwargs))
        messages = list(resource.get("messages") or [])
        last = messages[-1] if messages else {}
        headers = header_map(last) if last else {}
        sender_raw = header_value(headers, "From")
        subject = header_value(headers, "Subject")
        body: str | None = None
        if include_body and last:
            body = decode_body(last.get("payload") or {})
        return ThreadView(
            thread_id=str(resource.get("id") or thread_id),
            subject=subject,
            last_sender=extract_address(sender_raw) if sender_raw else sender_raw,
            last_message_at=message_datetime(last) if last else datetime.now(UTC),
            last_message_from_me=last_message_from_me(messages, self.account_email),
            snippet=str((last or resource).get("snippet") or ""),
            headers=headers,
            body=body,
        )

    def current_history_id(self) -> str | None:
        profile = self._execute(self._service.users().getProfile(userId="me"))
        history_id = profile.get("historyId")
        return str(history_id) if history_id else None

    def list_history_thread_ids(self, start_history_id: str) -> tuple[list[str], str | None]:
        thread_ids: list[str] = []
        seen: set[str] = set()
        page_token: str | None = None
        latest_id: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "userId": "me",
                "startHistoryId": start_history_id,
            }
            if page_token:
                kwargs["pageToken"] = page_token
            try:
                resp = self._execute(self._service.users().history().list(**kwargs))
            except HttpError as exc:
                if _http_status(exc) == 404:
                    raise HistoryExpiredError from exc
                raise
            latest_id = str(resp.get("historyId") or latest_id or "") or None
            for record in resp.get("history") or []:
                for message in record.get("messages") or []:
                    _collect_thread_id(seen, thread_ids, message.get("threadId"))
                for added in record.get("messagesAdded") or []:
                    msg = added.get("message") or {}
                    _collect_thread_id(seen, thread_ids, msg.get("threadId"))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return thread_ids, latest_id

    def fetch_for_sync(
        self,
        *,
        history_cursor: str | None,
        days: int = 30,
        limit: int = 100,
        newer_than: str | None = None,
        use_history: bool = True,
    ) -> SyncBatch:
        if use_history and history_cursor and not newer_than:
            try:
                thread_ids, history_id = self.list_history_thread_ids(history_cursor)
            except HistoryExpiredError:
                logger.info("gmail history expired; falling back to recent threads")
            else:
                views: list[ThreadView] = []
                for thread_id in thread_ids:
                    try:
                        views.append(self.get_thread(thread_id, include_body=False))
                    except HttpError as exc:
                        if _http_status(exc) == 404:
                            continue
                        raise
                return SyncBatch(
                    threads=views,
                    history_id=history_id or self.current_history_id(),
                    used_history=True,
                )
        views = self.list_recent_threads(
            days=days, limit=limit, include_body=False, newer_than=newer_than
        )
        return SyncBatch(
            threads=views,
            history_id=self.current_history_id(),
            used_history=False,
        )


def _collect_thread_id(seen: set[str], thread_ids: list[str], raw: Any) -> None:
    thread_id = str(raw or "")
    if thread_id and thread_id not in seen:
        seen.add(thread_id)
        thread_ids.append(thread_id)

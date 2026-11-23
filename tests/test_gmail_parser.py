import base64
from datetime import UTC, datetime

from app.gmail.parser import (
    decode_body,
    extract_address,
    header_map,
    last_message_from_me,
    message_datetime,
)


def _message(
    *,
    from_header: str,
    subject: str = "Hello",
    extra_headers: list[dict[str, str]] | None = None,
    internal_date: str = "1700000000000",
    body: str | None = None,
) -> dict:
    headers = [
        {"name": "From", "value": from_header},
        {"name": "To", "value": "me@example.com"},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": "Wed, 15 Nov 2023 10:00:00 +0000"},
    ]
    if extra_headers:
        headers.extend(extra_headers)
    payload: dict = {"mimeType": "text/plain", "headers": headers, "body": {}}
    if body is not None:
        payload["body"] = {
            "data": base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
        }
    return {"internalDate": internal_date, "snippet": "snipped", "payload": payload}


def test_extract_address_from_display_name() -> None:
    assert extract_address("Ada Lead <Ada@NewCo.example>") == "ada@newco.example"
    assert extract_address("me@example.com") == "me@example.com"


def test_header_parsing_keeps_metadata_headers() -> None:
    message = _message(
        from_header="News <digest@news.example>",
        extra_headers=[
            {"name": "List-Unsubscribe", "value": "<mailto:unsub@news.example>"},
            {"name": "Precedence", "value": "bulk"},
            {"name": "Auto-Submitted", "value": "auto-generated"},
        ],
    )
    headers = header_map(message)
    assert headers["List-Unsubscribe"] == "<mailto:unsub@news.example>"
    assert headers["Precedence"] == "bulk"
    assert headers["Auto-Submitted"] == "auto-generated"
    assert headers["Subject"] == "Hello"


def test_last_message_from_me_true_when_i_sent_last() -> None:
    messages = [
        _message(from_header="Ada <ada@x.com>"),
        _message(from_header="Me <me@example.com>"),
    ]
    assert last_message_from_me(messages, "me@example.com") is True


def test_last_message_from_me_false_when_they_sent_last() -> None:
    messages = [
        _message(from_header="Me <me@example.com>"),
        _message(from_header="Ada <ada@x.com>"),
    ]
    assert last_message_from_me(messages, "ME@example.com") is False


def test_message_datetime_from_internal_date() -> None:
    message = _message(from_header="a@b.com", internal_date="1700000000000")
    assert message_datetime(message) == datetime.fromtimestamp(1_700_000_000, tz=UTC)


def test_decode_body_only_when_present() -> None:
    with_body = _message(from_header="a@b.com", body="in-memory only")
    without = _message(from_header="a@b.com")
    assert decode_body(with_body["payload"]) == "in-memory only"
    assert decode_body(without["payload"]) == ""

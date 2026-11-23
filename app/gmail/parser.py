from __future__ import annotations

import base64
import email.utils
import re
from datetime import UTC, datetime
from typing import Any

METADATA_HEADERS = (
    "From",
    "To",
    "Subject",
    "Date",
    "List-Unsubscribe",
    "Precedence",
    "Auto-Submitted",
)


def extract_address(header_value: str) -> str:
    match = re.search(r"<([^>]+)>", header_value)
    return (match.group(1) if match else header_value).strip().lower()


def header_map(message: dict[str, Any]) -> dict[str, str]:
    wanted = {name.lower() for name in METADATA_HEADERS}
    headers: dict[str, str] = {}
    payload = message.get("payload") or {}
    for item in payload.get("headers") or []:
        name = str(item.get("name") or "")
        if name.lower() in wanted and name.lower() not in {k.lower() for k in headers}:
            headers[name] = str(item.get("value") or "")
    return headers


def header_value(headers: dict[str, str], name: str) -> str:
    needle = name.lower()
    for key, value in headers.items():
        if key.lower() == needle:
            return value
    return ""


def last_message_from_me(messages: list[dict[str, Any]], account_email: str) -> bool:
    if not messages:
        return False
    last = messages[-1]
    sender = header_value(header_map(last), "From")
    return extract_address(sender) == account_email.strip().lower()


def message_datetime(message: dict[str, Any]) -> datetime:
    internal = message.get("internalDate")
    if internal:
        return datetime.fromtimestamp(int(internal) / 1000, tz=UTC)
    date_header = header_value(header_map(message), "Date")
    if date_header:
        parsed = email.utils.parsedate_to_datetime(date_header)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    return datetime.now(UTC)


def decode_body(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    mime = str(payload.get("mimeType") or "")
    data = (payload.get("body") or {}).get("data")
    if mime.startswith("text/plain") and data:
        padded = str(data) + "=" * (-len(str(data)) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    for part in payload.get("parts") or []:
        text = decode_body(part)
        if text:
            return text
    if mime.startswith("text/html") and data:
        padded = str(data) + "=" * (-len(str(data)) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    return ""

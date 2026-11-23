from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.config import get_settings

HEADERS = (
    "id",
    "plan",
    "alert_email",
    "mailboxes",
    "whatsapp",
    "telegram",
    "timezone",
    "alert_hour",
    "updated_at",
)
SHEET = "subscribers"
_LOCK = threading.Lock()
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class RegistryRow:
    id: str
    plan: str
    alert_email: str
    mailboxes: list[str] = field(default_factory=list)
    whatsapp: str = ""
    telegram: str = ""
    timezone: str = "Asia/Kolkata"
    alert_hour: int = 9
    updated_at: str = ""

    def to_cells(self) -> list[str | int]:
        return [
            self.id,
            self.plan,
            self.alert_email,
            ";".join(self.mailboxes),
            self.whatsapp,
            self.telegram,
            self.timezone,
            self.alert_hour,
            self.updated_at,
        ]


def registry_path() -> Path:
    return Path(get_settings().registry_path)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def parse_mailbox_list(raw: str) -> list[str]:
    emails: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[;,\n]+", raw or ""):
        email = normalize_email(part)
        if email and email not in seen and _EMAIL.match(email):
            seen.add(email)
            emails.append(email)
    return emails


def _ensure_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = SHEET
    sheet.append(list(HEADERS))
    book.save(path)


def _load_sheet(path: Path) -> tuple[Workbook, Worksheet]:
    _ensure_workbook(path)
    book = load_workbook(path)
    if SHEET in book.sheetnames:
        sheet = book[SHEET]
    else:
        sheet = book.active
        assert sheet is not None
    if sheet.max_row < 1 or sheet.cell(1, 1).value != HEADERS[0]:
        sheet.delete_rows(1, sheet.max_row)
        sheet.append(list(HEADERS))
    return book, sheet


def _row_from_values(values: list[object]) -> RegistryRow | None:
    padded = list(values) + [""] * (len(HEADERS) - len(values))
    ident = str(padded[0] or "").strip()
    if not ident or ident == HEADERS[0]:
        return None
    hour_raw = padded[7]
    try:
        hour = int(hour_raw) if hour_raw not in (None, "") else 9
    except (TypeError, ValueError):
        hour = 9
    return RegistryRow(
        id=ident,
        plan=str(padded[1] or "").strip() or "starter",
        alert_email=normalize_email(str(padded[2] or "")),
        mailboxes=parse_mailbox_list(str(padded[3] or "")),
        whatsapp=str(padded[4] or "").strip(),
        telegram=str(padded[5] or "").strip(),
        timezone=str(padded[6] or "").strip() or "Asia/Kolkata",
        alert_hour=hour,
        updated_at=str(padded[8] or ""),
    )


def list_rows() -> list[RegistryRow]:
    path = registry_path()
    with _LOCK:
        book, sheet = _load_sheet(path)
        rows: list[RegistryRow] = []
        for cells in sheet.iter_rows(min_row=2, values_only=True):
            row = _row_from_values(list(cells))
            if row is not None:
                rows.append(row)
        book.close()
        return rows


def _write_rows(path: Path, rows: list[RegistryRow]) -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = SHEET
    sheet.append(list(HEADERS))
    for row in rows:
        sheet.append(row.to_cells())
    book.save(path)


def _stamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def upsert_row(update: RegistryRow) -> RegistryRow:
    path = registry_path()
    update.alert_email = normalize_email(update.alert_email)
    update.mailboxes = parse_mailbox_list(";".join(update.mailboxes))
    update.updated_at = _stamp()
    with _LOCK:
        _ensure_workbook(path)
        book, sheet = _load_sheet(path)
        rows: list[RegistryRow] = []
        replaced = False
        for cells in sheet.iter_rows(min_row=2, values_only=True):
            row = _row_from_values(list(cells))
            if row is None:
                continue
            match_id = bool(update.id) and row.id == update.id
            match_email = (
                row.plan == update.plan
                and row.alert_email == update.alert_email
                and bool(update.alert_email)
            )
            if match_id or match_email:
                if not update.id:
                    update.id = row.id
                rows.append(update)
                replaced = True
            else:
                rows.append(row)
        if not replaced:
            if not update.id:
                update.id = uuid4().hex[:10]
            rows.append(update)
        book.close()
        _write_rows(path, rows)
        return update


def get_row(
    *,
    plan: str,
    alert_email: str | None = None,
    row_id: str | None = None,
) -> RegistryRow | None:
    alert = normalize_email(alert_email or "")
    for row in list_rows():
        if row_id and row.id == row_id:
            return row
        if row.plan == plan and (not alert or row.alert_email == alert):
            if alert or plan == "founder":
                return row
    return None


def get_or_create_founder() -> RegistryRow:
    existing = get_row(plan="founder")
    if existing is not None:
        return existing
    settings = get_settings()
    return upsert_row(
        RegistryRow(
            id="founder",
            plan="founder",
            alert_email="",
            timezone=settings.default_timezone,
            alert_hour=settings.digest_hour,
        )
    )


def add_mailbox(plan: str, alert_email: str, mailbox: str, *, max_mailboxes: int) -> RegistryRow:
    email = normalize_email(mailbox)
    if not _EMAIL.match(email):
        raise ValueError("Enter a valid email")
    row = get_row(plan=plan, alert_email=alert_email)
    if row is None and plan == "founder":
        row = get_or_create_founder()
    if row is None:
        row = RegistryRow(id="", plan=plan, alert_email=normalize_email(alert_email))
    if email not in row.mailboxes:
        if len(row.mailboxes) >= max_mailboxes:
            raise ValueError("Mailbox limit reached")
        row.mailboxes.append(email)
    return upsert_row(row)


def remove_mailbox(plan: str, alert_email: str, mailbox: str) -> RegistryRow:
    email = normalize_email(mailbox)
    row = get_row(plan=plan, alert_email=alert_email)
    if row is None and plan == "founder":
        row = get_or_create_founder()
    if row is None:
        raise ValueError("No registry row found")
    row.mailboxes = [item for item in row.mailboxes if item != email]
    return upsert_row(row)


def replace_mailbox(
    plan: str,
    alert_email: str,
    old: str,
    new: str,
    *,
    max_mailboxes: int,
) -> RegistryRow:
    old_email = normalize_email(old)
    new_email = normalize_email(new)
    if not _EMAIL.match(new_email):
        raise ValueError("Enter a valid email")
    row = get_row(plan=plan, alert_email=alert_email)
    if row is None and plan == "founder":
        row = get_or_create_founder()
    if row is None:
        raise ValueError("No registry row found")
    if old_email not in row.mailboxes:
        raise ValueError("Mailbox not found")
    updated = [new_email if item == old_email else item for item in row.mailboxes]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in updated:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    if len(deduped) > max_mailboxes:
        raise ValueError("Mailbox limit reached")
    row.mailboxes = deduped
    return upsert_row(row)

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Account
from app.db.session import get_session
from app.plans import max_mailboxes
from app.registry import (
    RegistryRow,
    add_mailbox,
    get_or_create_founder,
    get_row,
    normalize_email,
    remove_mailbox,
    replace_mailbox,
    upsert_row,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _page(
    request: Request,
    session: Session,
    *,
    connected: str | None = None,
    notice: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    settings = get_settings()
    accounts = list(
        session.scalars(
            select(Account)
            .where(Account.provider == "gmail")
            .order_by(Account.account_email)
        )
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "accounts": accounts,
            "connected": connected,
            "notice": notice,
            "error": error,
            "founder_alert_email": settings.founder_alert_email,
            "llm_model": settings.llm_model,
            "digest_hour": settings.digest_hour,
            "timezone": settings.default_timezone,
        },
    )


def _gmail_by_email(session: Session) -> dict[str, Account]:
    accounts = list(
        session.scalars(
            select(Account)
            .where(Account.provider == "gmail")
            .order_by(Account.account_email)
        )
    )
    return {account.account_email.lower(): account for account in accounts}


def disconnect_gmail_account(session: Session, email: str) -> int:
    target = normalize_email(email)
    accounts = [
        account
        for account in session.scalars(select(Account).where(Account.provider == "gmail"))
        if account.account_email.lower() == target
    ]
    for account in accounts:
        session.delete(account)
    session.flush()
    return len(accounts)


def _mailbox_payload(emails: list[str], gmail: dict[str, Account]) -> list[dict[str, str | None]]:
    payload: list[dict[str, str | None]] = []
    for email in emails:
        account = gmail.get(email)
        payload.append(
            {
                "email": email,
                "status": account.status if account is not None else "listed",
                "last_synced_at": account.last_synced_at.isoformat()
                if account is not None and account.last_synced_at is not None
                else None,
            }
        )
    return payload


def _row_json(row: RegistryRow, session: Session) -> dict[str, object]:
    gmail = _gmail_by_email(session)
    return {
        "id": row.id,
        "plan": row.plan,
        "alert_email": row.alert_email,
        "whatsapp": row.whatsapp,
        "telegram": row.telegram,
        "timezone": row.timezone,
        "alert_hour": row.alert_hour,
        "max_mailboxes": max_mailboxes(row.plan),
        "accounts": _mailbox_payload(row.mailboxes, gmail),
    }


def _safe_next(raw: str | None, default: str = "/register") -> str:
    value = (raw or default).strip() or default
    if not value.startswith("/") or value.startswith("//"):
        return default
    return value.split("?", 1)[0]


def _redirect_front(path: str, **params: str) -> RedirectResponse:
    origin = get_settings().frontend_origin.strip().rstrip("/")
    filtered = {key: value for key, value in params.items() if value}
    qs = urlencode(filtered, quote_via=quote)
    dest = f"{path}?{qs}" if qs else path
    return RedirectResponse(f"{origin}{dest}" if origin else dest, status_code=303)


def _load_plan_row(plan: str, alert_email: str) -> RegistryRow:
    if plan == "founder":
        return get_or_create_founder()
    row = get_row(plan=plan, alert_email=alert_email)
    if row is None:
        row = RegistryRow(id="", plan=plan, alert_email=normalize_email(alert_email))
    return row


@router.get("/accounts")
def list_accounts(session: Session = Depends(get_session)) -> dict[str, object]:
    settings = get_settings()
    accounts = list(
        session.scalars(
            select(Account)
            .where(Account.provider == "gmail")
            .order_by(Account.account_email)
        )
    )
    return {
        "founder_alert_email": settings.founder_alert_email,
        "digest_hour": settings.digest_hour,
        "timezone": settings.default_timezone,
        "accounts": [
            {
                "email": account.account_email,
                "status": account.status,
                "last_synced_at": account.last_synced_at.isoformat()
                if account.last_synced_at
                else None,
            }
            for account in accounts
        ],
    }


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    session: Session = Depends(get_session),
    connected: str | None = Query(default=None),
    notice: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    return _page(
        request, session, connected=connected, notice=notice, error=error
    )


def _empty_registry(plan: str, alert_email: str = "") -> dict[str, object]:
    settings = get_settings()
    return {
        "id": "",
        "plan": plan,
        "alert_email": normalize_email(alert_email),
        "whatsapp": "",
        "telegram": "",
        "timezone": settings.default_timezone,
        "alert_hour": settings.digest_hour,
        "max_mailboxes": max_mailboxes(plan),
        "accounts": [],
        "complete": False,
    }


@router.get("/registry")
def read_registry(
    session: Session = Depends(get_session),
    plan: str = Query(default="founder"),
    alert_email: str | None = Query(default=None),
) -> dict[str, object]:
    if plan == "founder":
        row = get_row(plan="founder")
        if row is None:
            return _empty_registry("founder")
        payload = _row_json(row, session)
        payload["complete"] = bool(row.alert_email)
        payload["digest_hour"] = row.alert_hour
        return payload
    if not alert_email:
        return _empty_registry(plan)
    row = get_row(plan=plan, alert_email=alert_email)
    if row is None:
        return _empty_registry(plan, alert_email)
    payload = _row_json(row, session)
    payload["complete"] = bool(row.alert_email)
    return payload


@router.post("/registry")
def save_registry(
    plan: str = Form(default="founder"),
    alert_email: str = Form(default=""),
    whatsapp: str = Form(default=""),
    telegram: str = Form(default=""),
    timezone: str = Form(default=""),
    alert_hour: int | None = Form(default=None),
    next: str = Form(default="/register"),
) -> RedirectResponse:
    dest = _safe_next(next)
    try:
        row = _load_plan_row(plan, alert_email)
        if alert_email.strip():
            row.alert_email = normalize_email(alert_email)
        row.whatsapp = whatsapp.strip()
        row.telegram = telegram.strip()
        if timezone.strip():
            row.timezone = timezone.strip()
        if alert_hour is not None:
            row.alert_hour = alert_hour
        saved = upsert_row(row)
        return _redirect_front(
            dest,
            plan=saved.plan,
            alert_email=saved.alert_email,
            notice="Saved alert email",
        )
    except Exception as exc:
        return _redirect_front(
            dest,
            plan=plan,
            alert_email=alert_email,
            error=str(exc)[:180],
        )


@router.post("/registry/mailboxes")
def mutate_mailbox(
    session: Session = Depends(get_session),
    action: str = Form(...),
    plan: str = Form(default="founder"),
    alert_email: str = Form(default=""),
    email: str = Form(default=""),
    old_email: str = Form(default=""),
    new_email: str = Form(default=""),
    next: str = Form(default="/register"),
) -> RedirectResponse:
    dest = _safe_next(next)
    limit = max_mailboxes(plan)
    key = alert_email
    if plan == "founder":
        key = get_or_create_founder().alert_email
    try:
        if action == "add":
            add_mailbox(plan, key, email, max_mailboxes=limit)
            notice = f"Added {normalize_email(email)}"
        elif action == "remove":
            remove_mailbox(plan, key, email)
            disconnect_gmail_account(session, email)
            notice = f"Removed {normalize_email(email)}"
        elif action == "replace":
            replace_mailbox(plan, key, old_email, new_email, max_mailboxes=limit)
            if normalize_email(old_email) != normalize_email(new_email):
                disconnect_gmail_account(session, old_email)
            notice = f"Updated {normalize_email(old_email)} → {normalize_email(new_email)}"
        else:
            raise ValueError("Unknown mailbox action")
        return _redirect_front(dest, plan=plan, alert_email=key, notice=notice)
    except Exception as exc:
        return _redirect_front(dest, plan=plan, alert_email=key, error=str(exc)[:180])


@router.post("/digest/run")
def run_digest_now(hours: int | None = Form(default=None)) -> RedirectResponse:
    from app.jobs.digest_job import run_founder_digest

    try:
        count, status = run_founder_digest(skip_sync=False, hours=hours)
        window = f"last {hours}h" if hours else "all tracked mail"
        notice = quote(f"Report {status} ({count} threads, {window})")
        return RedirectResponse(f"/?notice={notice}", status_code=303)
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        return RedirectResponse(f"/?error={quote(detail[:180])}", status_code=303)

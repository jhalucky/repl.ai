from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import string
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Account, User
from app.db.session import get_session
from app.gmail.crypto import encrypt_token
from app.gmail.errors import InvalidOAuthState

logger = logging.getLogger(__name__)

router = APIRouter()

SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "email",
)
STATE_TTL_SECONDS = 600
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def _state_secret() -> bytes:
    key = get_settings().token_encryption_key.strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "TOKEN_ENCRYPTION_KEY is not set. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ),
        )
    return key.encode("utf-8")


def generate_code_verifier() -> str:
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(128))


def create_oauth_state(
    *,
    now: float | None = None,
    secret: bytes | None = None,
    code_verifier: str | None = None,
) -> str:
    issued = time.time() if now is None else now
    payload_obj: dict[str, Any] = {
        "exp": issued + STATE_TTL_SECONDS,
        "n": secrets.token_urlsafe(16),
    }
    if code_verifier:
        payload_obj["cv"] = code_verifier
    payload = json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).rstrip(b"=")
    sig = hmac.new(secret or _state_secret(), body, hashlib.sha256).digest()
    return f"{body.decode('ascii')}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode('ascii')}"


def verify_oauth_state(
    state: str,
    *,
    now: float | None = None,
    secret: bytes | None = None,
) -> dict[str, Any]:
    try:
        body_b64, sig_b64 = state.split(".", 1)
    except ValueError as exc:
        raise InvalidOAuthState("malformed") from exc
    body = body_b64.encode("ascii")
    padding = b"=" * (-len(sig_b64) % 4)
    try:
        expected = hmac.new(secret or _state_secret(), body, hashlib.sha256).digest()
        given = base64.urlsafe_b64decode(sig_b64.encode("ascii") + padding)
    except (ValueError, OSError) as exc:
        raise InvalidOAuthState("malformed") from exc
    if not hmac.compare_digest(expected, given):
        raise InvalidOAuthState("tampered")
    pad_body = b"=" * (-len(body_b64) % 4)
    try:
        raw = base64.urlsafe_b64decode(body_b64.encode("ascii") + pad_body)
        data: dict[str, Any] = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidOAuthState("malformed") from exc
    exp = float(data.get("exp") or 0)
    current = time.time() if now is None else now
    if current > exp:
        raise InvalidOAuthState("expired")
    return data


def _prepare_oauthlib() -> None:
    # Google often returns extra aliases (email vs userinfo.email).
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    uri = get_settings().google_redirect_uri
    if uri.startswith("http://localhost") or uri.startswith("http://127.0.0.1"):
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def build_flow() -> Flow:
    settings = get_settings()
    _prepare_oauthlib()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set",
        )
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": GOOGLE_AUTH_ENDPOINT,
                "token_uri": GOOGLE_TOKEN_ENDPOINT,
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=list(SCOPES),
        redirect_uri=settings.google_redirect_uri,
    )


def google_authorization_url(state: str, *, code_verifier: str) -> str:
    flow = build_flow()
    flow.code_verifier = code_verifier
    url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return url


def complete_google_login(
    code: str, code_verifier: str | None = None
) -> tuple[str, str]:
    """Exchange the auth code. Returns (account_email, refresh_token). Never logs tokens."""
    flow = build_flow()
    try:
        kwargs: dict[str, Any] = {"code": code}
        if code_verifier:
            kwargs["code_verifier"] = code_verifier
        flow.fetch_token(**kwargs)
    except Exception as exc:
        logger.warning(
            "gmail oauth token exchange failed: %s %s",
            type(exc).__name__,
            getattr(exc, "description", None) or str(exc.__class__.__name__),
        )
        raise HTTPException(
            status_code=400,
            detail="Google login failed. Start again at /auth/google/start",
        ) from None
    credentials = flow.credentials
    refresh_token = credentials.refresh_token
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a refresh token. Reconnect and grant offline access.",
        )
    email = _account_email(credentials)
    return email, refresh_token


def email_from_id_token(raw: str | None) -> str:
    if not raw or raw.count(".") != 2:
        return ""
    payload_b64 = raw.split(".")[1]
    pad = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
    except (ValueError, json.JSONDecodeError):
        return ""
    return str(payload.get("email") or "").strip().lower()


def _account_email(credentials: Any) -> str:
    try:
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        email = str(profile.get("emailAddress") or "").strip().lower()
        if email:
            return email
    except HttpError as exc:
        status = int(getattr(getattr(exc, "resp", None), "status", 0) or 0)
        if status != 403:
            logger.warning("gmail profile failed: HTTP %s", status)
            raise HTTPException(
                status_code=400,
                detail="Google login failed. Start again at /auth/google/start",
            ) from None
        logger.warning("gmail API disabled; falling back to OpenID email")
    email = email_from_id_token(getattr(credentials, "id_token", None))
    if email:
        return email
    raise HTTPException(
        status_code=400,
        detail=(
            "Enable the Gmail API in Google Cloud Console, wait a few minutes, "
            "then start again at /auth/google/start"
        ),
    )


def upsert_gmail_account(session: Session, email: str, refresh_token: str) -> Account:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, timezone=get_settings().default_timezone)
        session.add(user)
        session.flush()
    account = session.scalar(
        select(Account).where(Account.user_id == user.id, Account.account_email == email)
    )
    encrypted = encrypt_token(refresh_token)
    if account is None:
        account = Account(
            user_id=user.id,
            provider="gmail",
            account_email=email,
            encrypted_refresh_token=encrypted,
            status="active",
        )
        session.add(account)
        session.flush()
    else:
        account.encrypted_refresh_token = encrypted
        account.status = "active"
        session.flush()
    return account


@router.get("/auth/google/start")
def google_start() -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set",
        )
    code_verifier = generate_code_verifier()
    state = create_oauth_state(code_verifier=code_verifier)
    logger.info("gmail oauth start")
    return RedirectResponse(
        google_authorization_url(state, code_verifier=code_verifier),
        status_code=302,
    )


@router.get("/auth/google/callback")
def google_callback(
    session: Session = Depends(get_session),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail="Google authorization was denied")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")
    try:
        payload = verify_oauth_state(state)
    except InvalidOAuthState:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from None
    verifier = payload.get("cv")
    if not isinstance(verifier, str) or not verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    email, refresh_token = complete_google_login(code, verifier)
    account = upsert_gmail_account(session, email, refresh_token)
    logger.info("gmail account connected id=%s", account.id)
    try:
        from app.plans import max_mailboxes
        from app.registry import add_mailbox, get_or_create_founder

        founder = get_or_create_founder()
        add_mailbox(
            "founder",
            founder.alert_email,
            email,
            max_mailboxes=max_mailboxes("founder"),
        )
    except Exception:
        logger.warning("registry mailbox skip email=%s", email)
    origin = get_settings().frontend_origin.strip().rstrip("/")
    dest = f"{origin}/register" if origin else "/register"
    return RedirectResponse(f"{dest}?plan=founder&connected={email}", status_code=303)

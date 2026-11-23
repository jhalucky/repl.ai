from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, User
from app.gmail.crypto import decrypt_token
from app.gmail.errors import InvalidOAuthState
from app.gmail.oauth import (
    STATE_TTL_SECONDS,
    create_oauth_state,
    email_from_id_token,
    upsert_gmail_account,
    verify_oauth_state,
)

SECRET = b"test-oauth-state-secret-key"


def test_email_from_id_token() -> None:
    import base64
    import json

    payload = base64.urlsafe_b64encode(
        json.dumps({"email": "Founder@Example.com"}).encode()
    ).rstrip(b"=").decode()
    token = f"eyJhbGciOiJub25lIn0.{payload}.sig"
    assert email_from_id_token(token) == "founder@example.com"
    assert email_from_id_token(None) == ""
    assert email_from_id_token("not-a-jwt") == ""


def test_oauth_state_valid() -> None:
    state = create_oauth_state(now=1_700_000_000, secret=SECRET)
    payload = verify_oauth_state(state, now=1_700_000_000 + 10, secret=SECRET)
    assert "exp" in payload


def test_oauth_state_preserves_code_verifier() -> None:
    state = create_oauth_state(
        now=1_700_000_000, secret=SECRET, code_verifier="pkce-secret-verifier"
    )
    payload = verify_oauth_state(state, now=1_700_000_000 + 10, secret=SECRET)
    assert payload["cv"] == "pkce-secret-verifier"


def test_oauth_state_tampered() -> None:
    state = create_oauth_state(now=1_700_000_000, secret=SECRET)
    body, sig = state.split(".", 1)
    tampered = body[:-1] + ("A" if body[-1] != "A" else "B") + "." + sig
    with pytest.raises(InvalidOAuthState):
        verify_oauth_state(tampered, now=1_700_000_000 + 10, secret=SECRET)


def test_oauth_state_expired() -> None:
    now = 1_700_000_000
    state = create_oauth_state(now=now, secret=SECRET)
    with pytest.raises(InvalidOAuthState, match="expired"):
        verify_oauth_state(state, now=now + STATE_TTL_SECONDS + 1, secret=SECRET)


def test_start_redirects_to_google_with_offline_consent(client: TestClient) -> None:
    response = client.get("/auth/google/start", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    parsed = urlparse(location)
    assert parsed.netloc == "accounts.google.com"
    query = parse_qs(parsed.query)
    scopes = " ".join(query.get("scope", []))
    assert "gmail.readonly" in scopes
    assert "openid" in scopes
    assert query.get("access_type") == ["offline"]
    assert query.get("prompt") == ["consent"]
    assert query.get("state")
    assert query.get("code_challenge_method") == ["S256"]
    assert query.get("code_challenge")


def test_callback_rejects_tampered_state(client: TestClient) -> None:
    response = client.get(
        "/auth/google/callback",
        params={"code": "abc", "state": "not-a-valid-state"},
    )
    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()


def test_callback_upserts_user_and_encrypted_token(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.gmail.oauth.complete_google_login",
        lambda code, code_verifier=None: ("founder@example.com", "refresh-token-secret"),
    )
    state = create_oauth_state(code_verifier="pkce-verifier")
    response = client.get(
        "/auth/google/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "/register?plan=founder&connected=founder@example.com"
    )
    assert "refresh-token-secret" not in response.text

    user = db_session.scalar(select(User).where(User.email == "founder@example.com"))
    assert user is not None
    account = db_session.scalar(select(Account).where(Account.user_id == user.id))
    assert account is not None
    assert account.provider == "gmail"
    assert account.status == "active"
    assert account.encrypted_refresh_token != "refresh-token-secret"
    assert decrypt_token(account.encrypted_refresh_token) == "refresh-token-secret"


def test_upsert_reconnects_existing_account(db_session: Session) -> None:
    account = upsert_gmail_account(db_session, "me@example.com", "first-token")
    account.status = "needs_reconnect"
    db_session.flush()
    updated = upsert_gmail_account(db_session, "me@example.com", "second-token")
    assert updated.id == account.id
    assert updated.status == "active"
    assert decrypt_token(updated.encrypted_refresh_token) == "second-token"
    assert len(list(db_session.scalars(select(User)))) == 1
    assert len(list(db_session.scalars(select(Account)))) == 1

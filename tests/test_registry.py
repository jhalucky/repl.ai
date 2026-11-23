from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, User
from app.gmail.crypto import encrypt_token
from app.registry import add_mailbox, get_or_create_founder, list_rows, registry_path


@pytest.fixture(autouse=True)
def _fresh_registry() -> None:
    path = registry_path()
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


def test_founder_registry_empty_until_saved(client: TestClient) -> None:
    response = client.get("/registry", params={"plan": "founder"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"] == "founder"
    assert payload["alert_email"] == ""
    assert payload["complete"] is False
    assert payload["accounts"] == []


def test_founder_save_writes_sheet(client: TestClient) -> None:
    response = client.post(
        "/registry",
        data={
            "plan": "founder",
            "alert_email": "founder@example.com",
            "whatsapp": "+919876543210",
            "telegram": "@founder",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Saved%20alert%20email" in response.headers["location"]
    payload = client.get("/registry", params={"plan": "founder"}).json()
    assert payload["complete"] is True
    assert payload["alert_email"] == "founder@example.com"
    assert payload["whatsapp"] == "+919876543210"
    assert payload["telegram"] == "@founder"
    assert registry_path().exists()


def test_founder_can_add_mailbox_before_alert_email(client: TestClient) -> None:
    response = client.post(
        "/registry/mailboxes",
        data={
            "action": "add",
            "plan": "founder",
            "email": "inbox@gmail.com",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    payload = client.get("/registry", params={"plan": "founder"}).json()
    assert payload["alert_email"] == ""
    assert payload["complete"] is False
    assert payload["accounts"][0]["email"] == "inbox@gmail.com"


def test_add_and_remove_mailbox(client: TestClient) -> None:
    add = client.post(
        "/registry/mailboxes",
        data={
            "action": "add",
            "plan": "starter",
            "alert_email": "ops@example.com",
            "email": "box@example.com",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert add.status_code == 303
    rows = list_rows()
    assert any("box@example.com" in row.mailboxes for row in rows)

    remove = client.post(
        "/registry/mailboxes",
        data={
            "action": "remove",
            "plan": "starter",
            "alert_email": "ops@example.com",
            "email": "box@example.com",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert remove.status_code == 303
    rows = list_rows()
    starter = next(row for row in rows if row.alert_email == "ops@example.com")
    assert "box@example.com" not in starter.mailboxes


def test_remove_mailbox_disconnects_gmail(client: TestClient, db_session: Session) -> None:
    user = User(email="ops@example.com")
    db_session.add(user)
    db_session.flush()
    db_session.add(
        Account(
            user_id=user.id,
            account_email="ops@example.com",
            encrypted_refresh_token=encrypt_token("refresh"),
            status="active",
        )
    )
    db_session.flush()
    founder = get_or_create_founder()
    add_mailbox("founder", founder.alert_email, "ops@example.com", max_mailboxes=20)

    response = client.post(
        "/registry/mailboxes",
        data={
            "action": "remove",
            "plan": "founder",
            "email": "ops@example.com",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.expire_all()
    leftover = list(
        db_session.scalars(select(Account).where(Account.account_email == "ops@example.com"))
    )
    assert leftover == []


def test_replace_mailbox(client: TestClient) -> None:
    client.post(
        "/registry/mailboxes",
        data={
            "action": "add",
            "plan": "base",
            "alert_email": "lead@example.com",
            "email": "old@example.com",
            "next": "/register",
        },
        follow_redirects=False,
    )
    response = client.post(
        "/registry/mailboxes",
        data={
            "action": "replace",
            "plan": "base",
            "alert_email": "lead@example.com",
            "old_email": "old@example.com",
            "new_email": "new@example.com",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = next(item for item in list_rows() if item.alert_email == "lead@example.com")
    assert "new@example.com" in row.mailboxes
    assert "old@example.com" not in row.mailboxes


def test_save_alert_channels(client: TestClient) -> None:
    response = client.post(
        "/registry",
        data={
            "plan": "base",
            "alert_email": "lead@example.com",
            "whatsapp": "+919999999999",
            "telegram": "@lead",
            "next": "/register",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    payload = client.get(
        "/registry", params={"plan": "base", "alert_email": "lead@example.com"}
    ).json()
    assert payload["whatsapp"] == "+919999999999"
    assert payload["telegram"] == "@lead"


def test_registry_file_is_xlsx() -> None:
    get_or_create_founder()
    path = registry_path()
    assert path.suffix == ".xlsx"
    assert Path(path).stat().st_size > 0

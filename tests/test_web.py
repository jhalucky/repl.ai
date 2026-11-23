from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Account, User
from app.gmail.crypto import encrypt_token


def test_home_lists_accounts_and_connect(client: TestClient, db_session: Session) -> None:
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

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Connect another Gmail" in response.text
    assert "ops@example.com" in response.text
    assert "/auth/google/start" in response.text


def test_home_has_last_hour_test(client: TestClient) -> None:
    response = client.get("/")
    assert "Test last hour" in response.text
    assert 'name="hours"' in response.text
    assert 'value="1"' in response.text


def test_accounts_json_lists_gmail(client: TestClient, db_session: Session) -> None:
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

    response = client.get("/accounts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["accounts"][0]["email"] == "ops@example.com"
    assert payload["accounts"][0]["status"] == "active"


def test_home_shows_connected_query(client: TestClient) -> None:
    response = client.get("/", params={"connected": "ops@example.com"})
    assert response.status_code == 200
    assert "Connected ops@example.com" in response.text

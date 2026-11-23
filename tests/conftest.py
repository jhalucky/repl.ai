import os
from collections.abc import Generator

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://inboxguard:inboxguard@localhost:5434/inboxguard_test",
)
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ["FRONTEND_ORIGIN"] = ""
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["REGISTRY_PATH"] = str(
    __import__("pathlib").Path(__file__).resolve().parent / "_tmp_replai_registry.xlsx"
)

import time  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.engine.url import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402

TABLES = (
    "users",
    "accounts",
    "threads",
    "classifications",
    "alerts",
    "feedback",
    "sender_stats",
)


def _wait_for_postgres(url_str: str, attempts: int = 30) -> None:
    url = make_url(url_str)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with admin_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            admin_engine.dispose()
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)
    admin_engine.dispose()
    raise RuntimeError("Postgres is not reachable. Run: docker compose up -d") from last_error


def _ensure_database(url_str: str) -> None:
    url = make_url(url_str)
    db_name = url.database
    if db_name is None:
        raise RuntimeError("DATABASE_URL must include a database name")

    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()


def _reset_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def pytest_configure() -> None:
    url = os.environ["DATABASE_URL"]
    _wait_for_postgres(url)
    _ensure_database(url)
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    _reset_schema(engine)
    engine.dispose()
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture()
def db_engine() -> Generator[Engine, None, None]:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    session = Session(bind=db_engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

import sqlalchemy as sa
from sqlalchemy.engine import Engine

EXPECTED_TABLES = {
    "alembic_version",
    "users",
    "accounts",
    "threads",
    "classifications",
    "alerts",
    "feedback",
    "sender_stats",
}


def test_alembic_upgrade_creates_all_tables(db_engine: Engine) -> None:
    inspector = sa.inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= tables


def test_alembic_version_is_head(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0002_account_status"


def test_accounts_status_column_exists(db_engine: Engine) -> None:
    inspector = sa.inspect(db_engine)
    columns = {column["name"] for column in inspector.get_columns("accounts")}
    assert "status" in columns


def test_threads_unique_constraint_exists(db_engine: Engine) -> None:
    inspector = sa.inspect(db_engine)
    uniques = inspector.get_unique_constraints("threads")
    names = {constraint["name"] for constraint in uniques}
    assert "uq_threads_account_provider" in names

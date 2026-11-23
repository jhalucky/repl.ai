"""Add accounts.status for Gmail reconnect.

Revision ID: 0002_account_status
Revises: 0001_initial
Create Date: 2026-11-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_account_status"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.create_check_constraint(
        "ck_accounts_status",
        "accounts",
        "status IN ('active', 'needs_reconnect')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_accounts_status", "accounts", type_="check")
    op.drop_column("accounts", "status")

"""Index governed Agent Tools cash-cut compensation reads.

Revision ID: 0081_agent_cash_cut_compensation_index
Revises: 0080_agent_purchase_history_indexes
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0081_agent_cash_cut_compensation_index"
down_revision: str | None = "0080_agent_purchase_history_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMPENSATION_INDEX = "ix_agent_cash_cut_compensations_org_cut_created_id"


def upgrade() -> None:
    concurrently = op.get_bind().dialect.name == "postgresql"
    if concurrently:
        with op.get_context().autocommit_block():
            op.create_index(
                COMPENSATION_INDEX,
                "user_cash_cut_compensations",
                ["organization_id", "cash_cut_id", "created_at", "id"],
                unique=False,
                postgresql_concurrently=True,
            )
    else:
        op.create_index(
            COMPENSATION_INDEX,
            "user_cash_cut_compensations",
            ["organization_id", "cash_cut_id", "created_at", "id"],
            unique=False,
        )


def downgrade() -> None:
    concurrently = op.get_bind().dialect.name == "postgresql"
    if concurrently:
        with op.get_context().autocommit_block():
            op.drop_index(
                COMPENSATION_INDEX,
                table_name="user_cash_cut_compensations",
                postgresql_concurrently=True,
            )
    else:
        op.drop_index(COMPENSATION_INDEX, table_name="user_cash_cut_compensations")

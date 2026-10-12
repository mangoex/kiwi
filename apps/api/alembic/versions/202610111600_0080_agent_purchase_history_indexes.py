"""Index governed Agent Tools purchase history reads.

Revision ID: 0080_agent_purchase_history_indexes
Revises: 0079_agent_inventory_movement_index
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0080_agent_purchase_history_indexes"
down_revision: str | None = "0079_agent_inventory_movement_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOCUMENT_INDEX = "ix_agent_purchase_history_org_branch_confirmed_id"
LINE_INDEX = "ix_agent_purchase_lines_document_id"


def upgrade() -> None:
    concurrently = op.get_bind().dialect.name == "postgresql"
    if concurrently:
        with op.get_context().autocommit_block():
            op.create_index(
                DOCUMENT_INDEX,
                "purchase_documents",
                ["organization_id", "branch_id", "confirmed_at", "id"],
                unique=False,
                postgresql_concurrently=True,
            )
            op.create_index(
                LINE_INDEX,
                "purchase_document_lines",
                ["purchase_document_id", "id"],
                unique=False,
                postgresql_concurrently=True,
            )
    else:
        op.create_index(
            DOCUMENT_INDEX,
            "purchase_documents",
            ["organization_id", "branch_id", "confirmed_at", "id"],
            unique=False,
        )
        op.create_index(
            LINE_INDEX,
            "purchase_document_lines",
            ["purchase_document_id", "id"],
            unique=False,
        )


def downgrade() -> None:
    concurrently = op.get_bind().dialect.name == "postgresql"
    if concurrently:
        with op.get_context().autocommit_block():
            op.drop_index(
                LINE_INDEX,
                table_name="purchase_document_lines",
                postgresql_concurrently=True,
            )
            op.drop_index(
                DOCUMENT_INDEX,
                table_name="purchase_documents",
                postgresql_concurrently=True,
            )
    else:
        op.drop_index(LINE_INDEX, table_name="purchase_document_lines")
        op.drop_index(DOCUMENT_INDEX, table_name="purchase_documents")

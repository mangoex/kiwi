"""Index scoped Agent Tools inventory movement reads.

Revision ID: 0079_agent_inventory_movement_index
Revises: 0078_grokbot_agent_tools
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0079_agent_inventory_movement_index"
down_revision: str | None = "0078_grokbot_agent_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_inventory_movements_org_branch_effective_id"


def upgrade() -> None:
    concurrently = op.get_bind().dialect.name == "postgresql"
    if concurrently:
        with op.get_context().autocommit_block():
            op.create_index(
                INDEX_NAME,
                "inventory_movements",
                ["organization_id", "branch_id", "effective_at", "id"],
                unique=False,
                postgresql_concurrently=True,
            )
    else:
        op.create_index(
            INDEX_NAME,
            "inventory_movements",
            ["organization_id", "branch_id", "effective_at", "id"],
            unique=False,
        )


def downgrade() -> None:
    concurrently = op.get_bind().dialect.name == "postgresql"
    if concurrently:
        with op.get_context().autocommit_block():
            op.drop_index(
                INDEX_NAME,
                table_name="inventory_movements",
                postgresql_concurrently=True,
            )
    else:
        op.drop_index(INDEX_NAME, table_name="inventory_movements")

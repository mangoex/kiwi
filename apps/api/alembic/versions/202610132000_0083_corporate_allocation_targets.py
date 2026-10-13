"""Freeze exact allocation targets without rewriting historical purchases."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0083_corporate_allocation_targets"
down_revision: str | None = "0082_corporate_purchase_orders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("corporate_purchase_orders") as batch:
        batch.add_column(
            sa.Column("allocation_policy_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_check_constraint(
            "ck_corporate_allocation_policy", "allocation_policy_version IN (1, 2)"
        )
    with op.batch_alter_table("corporate_purchase_allocations") as batch:
        batch.add_column(sa.Column("allocation_sequence", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("inventory_cost_target", sa.Numeric(18, 6), nullable=True))
        batch.create_unique_constraint(
            "uq_corporate_allocation_sequence", ["order_line_id", "allocation_sequence"]
        )
        batch.create_check_constraint(
            "ck_corporate_allocation_targets",
            "(allocation_sequence IS NULL AND inventory_cost_target IS NULL) OR "
            "(allocation_sequence >= 0 AND inventory_cost_target >= 0 AND "
            "allocation_sequence IS NOT NULL AND inventory_cost_target IS NOT NULL)",
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM corporate_purchase_orders WHERE allocation_policy_version = 2"
        )
    ) or connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM corporate_purchase_allocations "
            "WHERE allocation_sequence IS NOT NULL OR inventory_cost_target IS NOT NULL"
        )
    ):
        raise RuntimeError("Cannot downgrade 0083 while frozen allocation history exists")
    with op.batch_alter_table("corporate_purchase_allocations") as batch:
        batch.drop_constraint("ck_corporate_allocation_targets", type_="check")
        batch.drop_constraint("uq_corporate_allocation_sequence", type_="unique")
        batch.drop_column("inventory_cost_target")
        batch.drop_column("allocation_sequence")
    with op.batch_alter_table("corporate_purchase_orders") as batch:
        batch.drop_constraint("ck_corporate_allocation_policy", type_="check")
        batch.drop_column("allocation_policy_version")

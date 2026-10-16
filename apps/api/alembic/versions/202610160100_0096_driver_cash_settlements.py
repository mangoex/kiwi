"""driver cash settlements

Revision ID: 0096_driver_cash_settlements
Revises: 0095_branch_product_digital_visibility
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0096_driver_cash_settlements"
down_revision: str | None = "0095_branch_product_digital_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "driver_cash_settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("driver_name_snapshot", sa.String(160), nullable=False),
        sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
        sa.Column("register_code_snapshot", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status = 'CONFIRMED'", name="ck_driver_cash_settlements_status"),
        sa.CheckConstraint(
            "order_count BETWEEN 1 AND 100 AND total_cents > 0",
            name="ck_driver_cash_settlements_amounts",
        ),
    )
    op.create_index(
        "ix_driver_cash_settlements_scope_confirmed",
        "driver_cash_settlements",
        ["organization_id", "branch_id", "driver_id", "confirmed_at"],
    )
    op.create_table(
        "driver_cash_settlement_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("settlement_id", sa.String(36), sa.ForeignKey("driver_cash_settlements.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False, unique=True),
        sa.Column("folio_snapshot", sa.String(64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_driver_cash_settlement_items_amount"),
    )
    op.create_index(
        "ix_driver_cash_settlement_items_settlement",
        "driver_cash_settlement_items",
        ["settlement_id", "order_id"],
    )
    op.create_table(
        "driver_cash_settlement_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("settlement_id", sa.String(36), sa.ForeignKey("driver_cash_settlements.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_driver_cash_settlement_command_org_key"
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_driver_cash_settlement_command_hash"),
    )
    op.create_index(
        "ix_driver_cash_settlement_commands_scope_created",
        "driver_cash_settlement_commands",
        ["organization_id", "branch_id", "created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE driver_cash_settlements, "
                "driver_cash_settlement_items, "
                "driver_cash_settlement_commands IN ACCESS EXCLUSIVE MODE"
            )
        )
    for table_name in (
        "driver_cash_settlement_commands",
        "driver_cash_settlement_items",
        "driver_cash_settlements",
    ):
        if bind.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")).first():
            raise RuntimeError(
                "0096 downgrade blocked: driver cash settlement history exists"
            )
    op.drop_index(
        "ix_driver_cash_settlement_commands_scope_created",
        table_name="driver_cash_settlement_commands",
    )
    op.drop_table("driver_cash_settlement_commands")
    op.drop_index(
        "ix_driver_cash_settlement_items_settlement",
        table_name="driver_cash_settlement_items",
    )
    op.drop_table("driver_cash_settlement_items")
    op.drop_index(
        "ix_driver_cash_settlements_scope_confirmed",
        table_name="driver_cash_settlements",
    )
    op.drop_table("driver_cash_settlements")

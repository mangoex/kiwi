"""Add POS handoffs and idempotent order/payment commands.

Revision ID: 0052_pos_handoff_and_idempotency
Revises: 0051_public_order_intents
"""

from collections.abc import Sequence
from typing import Optional

import sqlalchemy as sa
from alembic import context, op

revision = "0052_pos_handoff_and_idempotency"
down_revision = "0051_public_order_intents"
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "pos_session_handoffs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_app", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("target_app = 'pos'", name="ck_pos_session_handoff_target"),
        sa.CheckConstraint("length(code_hash) = 64", name="ck_pos_session_handoff_hash"),
    )
    op.create_index(
        "ix_pos_session_handoffs_user_expires",
        "pos_session_handoffs",
        ["organization_id", "user_id", "expires_at"],
    )
    op.create_table(
        "order_create_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_order_create_command_org_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_order_create_command_hash"),
    )
    op.create_index(
        "ix_order_create_commands_scope_created",
        "order_create_commands",
        ["organization_id", "branch_id", "created_at"],
    )
    if not context.is_offline_mode():
        bind = op.get_bind()
        duplicate = bind.execute(
            sa.text(
                "SELECT order_id FROM payments WHERE status = 'CONFIRMED' "
                "GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate:
            raise RuntimeError("Duplicate confirmed payments block payment idempotency migration")
    op.create_index(
        "uq_payments_confirmed_order",
        "payments",
        ["order_id"],
        unique=True,
        sqlite_where=sa.text("status = 'CONFIRMED'"),
        postgresql_where=sa.text("status = 'CONFIRMED'"),
    )
    op.create_table(
        "payment_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_payment_command_org_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_payment_command_hash"),
    )
    op.create_index(
        "ix_payment_commands_scope_created",
        "payment_commands",
        ["organization_id", "branch_id", "created_at"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        guarded_tables = (
            ("payment_commands", "Payment command history blocks downgrade"),
            ("order_create_commands", "Order creation command history blocks downgrade"),
            ("pos_session_handoffs", "POS session handoff audit history blocks downgrade"),
        )
        for table_name, message in guarded_tables:
            if bind.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")).first():
                raise RuntimeError(message)
    op.drop_index("ix_payment_commands_scope_created", table_name="payment_commands")
    op.drop_table("payment_commands")
    op.drop_index("uq_payments_confirmed_order", table_name="payments")
    op.drop_index("ix_order_create_commands_scope_created", table_name="order_create_commands")
    op.drop_table("order_create_commands")
    op.drop_index("ix_pos_session_handoffs_user_expires", table_name="pos_session_handoffs")
    op.drop_table("pos_session_handoffs")

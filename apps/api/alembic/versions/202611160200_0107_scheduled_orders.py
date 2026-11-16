"""Add scheduled_for support to orders and public_order_intents."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0107_scheduled_orders"
down_revision = "0106_branch_operating_hours"
branch_labels = depends_on = None

_OLD_CK = (
    "cash_shift_id IS NOT NULL OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI', 'WHATSAPP') "
    "OR (channel = 'PUBLIC_INTENT' "
    "AND public_order_intent_id IS NOT NULL "
    "AND public_order_intent_status = 'ACCEPTED')"
)
_NEW_CK = (
    "cash_shift_id IS NOT NULL "
    "OR status = 'SCHEDULED' "
    "OR (status = 'CANCELLED' AND scheduled_for IS NOT NULL) "
    "OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI', 'WHATSAPP') "
    "OR (channel = 'PUBLIC_INTENT' "
    "AND public_order_intent_id IS NOT NULL "
    "AND public_order_intent_status = 'ACCEPTED')"
)


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("scheduled_released_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("scheduled_released_by_user_id", sa.String(36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_orders_scheduled_released_by_user_id_users",
            "users",
            ["scheduled_released_by_user_id"],
            ["id"],
        )
        batch_op.drop_constraint(
            "ck_orders_cash_shift_required_except_public_intent", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_orders_cash_shift_required_except_public_intent", _NEW_CK
        )
        batch_op.create_index(
            "ix_orders_branch_status_scheduled_for",
            ["branch_id", "status", "scheduled_for"],
        )

    with op.batch_alter_table("public_order_intents") as batch_op:
        batch_op.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("public_order_intents") as batch_op:
        batch_op.drop_column("scheduled_for")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_branch_status_scheduled_for")
        batch_op.drop_constraint(
            "ck_orders_cash_shift_required_except_public_intent", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_orders_cash_shift_required_except_public_intent", _OLD_CK
        )
        batch_op.drop_constraint(
            "fk_orders_scheduled_released_by_user_id_users", type_="foreignkey"
        )
        batch_op.drop_column("scheduled_released_by_user_id")
        batch_op.drop_column("scheduled_released_at")
        batch_op.drop_column("scheduled_for")

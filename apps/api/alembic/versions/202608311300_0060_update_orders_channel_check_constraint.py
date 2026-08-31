"""Update orders check constraint to support marketplace channels.

Revision ID: 0060_update_orders_channel_check_constraint
Revises: 0059_channel_integrations_uber_eats
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0060_update_orders_channel_check_constraint"
down_revision: str | None = "0059_channel_integrations_uber_eats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use raw SQL to cleanly drop and recreate check constraint in PostgreSQL and SQLite
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cash_shift_required_except_public_intent")
        op.execute(
            "ALTER TABLE orders ADD CONSTRAINT ck_orders_cash_shift_required_except_public_intent "
            "CHECK (cash_shift_id IS NOT NULL OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI') "
            "OR (channel = 'PUBLIC_INTENT' AND public_order_intent_id IS NOT NULL AND public_order_intent_status = 'ACCEPTED'))"
        )
    else:
        with op.batch_alter_table("orders") as batch:
            try:
                batch.drop_constraint("ck_orders_cash_shift_required_except_public_intent", type_="check")
            except Exception:
                pass
            batch.create_check_constraint(
                "ck_orders_cash_shift_required_except_public_intent",
                "cash_shift_id IS NOT NULL OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI') "
                "OR (channel = 'PUBLIC_INTENT' "
                "AND public_order_intent_id IS NOT NULL "
                "AND public_order_intent_status = 'ACCEPTED')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cash_shift_required_except_public_intent")
        op.execute(
            "ALTER TABLE orders ADD CONSTRAINT ck_orders_cash_shift_required_except_public_intent "
            "CHECK (cash_shift_id IS NOT NULL OR (channel = 'PUBLIC_INTENT' AND public_order_intent_id IS NOT NULL AND public_order_intent_status = 'ACCEPTED'))"
        )
    else:
        with op.batch_alter_table("orders") as batch:
            try:
                batch.drop_constraint("ck_orders_cash_shift_required_except_public_intent", type_="check")
            except Exception:
                pass
            batch.create_check_constraint(
                "ck_orders_cash_shift_required_except_public_intent",
                "cash_shift_id IS NOT NULL OR (channel = 'PUBLIC_INTENT' "
                "AND public_order_intent_id IS NOT NULL "
                "AND public_order_intent_status = 'ACCEPTED')",
            )

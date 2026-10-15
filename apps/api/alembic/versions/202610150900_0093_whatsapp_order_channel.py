"""WhatsApp order channel and Asistto integration config.

Revision ID: 0093_whatsapp_order_channel
Revises: 0092_supplier_xml_imports
"""

from __future__ import annotations

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "0093_whatsapp_order_channel"
down_revision: str | None = "0092_supplier_xml_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cash_shift_required_except_public_intent")
        op.execute(
            "ALTER TABLE orders ADD CONSTRAINT ck_orders_cash_shift_required_except_public_intent "
            "CHECK (cash_shift_id IS NOT NULL OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI', 'WHATSAPP') "
            "OR (channel = 'PUBLIC_INTENT' AND public_order_intent_id IS NOT NULL AND public_order_intent_status = 'ACCEPTED'))"
        )
        op.add_column("channel_integrations", sa.Column("return_url", sa.String(500), nullable=True))
        op.add_column("channel_integrations", sa.Column("master_prompt", sa.Text(), nullable=True))
    else:
        with op.batch_alter_table("orders") as batch:
            try:
                batch.drop_constraint("ck_orders_cash_shift_required_except_public_intent", type_="check")
            except Exception:
                pass
            batch.create_check_constraint(
                "ck_orders_cash_shift_required_except_public_intent",
                "cash_shift_id IS NOT NULL OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI', 'WHATSAPP') "
                "OR (channel = 'PUBLIC_INTENT' "
                "AND public_order_intent_id IS NOT NULL "
                "AND public_order_intent_status = 'ACCEPTED')",
            )
        with op.batch_alter_table("channel_integrations") as batch:
            batch.add_column(sa.Column("return_url", sa.String(500), nullable=True))
            batch.add_column(sa.Column("master_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cash_shift_required_except_public_intent")
        op.execute(
            "ALTER TABLE orders ADD CONSTRAINT ck_orders_cash_shift_required_except_public_intent "
            "CHECK (cash_shift_id IS NOT NULL OR channel IN ('UBER_EATS', 'DIDI_FOOD', 'RAPPI') "
            "OR (channel = 'PUBLIC_INTENT' AND public_order_intent_id IS NOT NULL AND public_order_intent_status = 'ACCEPTED'))"
        )
        op.drop_column("channel_integrations", "master_prompt")
        op.drop_column("channel_integrations", "return_url")
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
        with op.batch_alter_table("channel_integrations") as batch:
            batch.drop_column("master_prompt")
            batch.drop_column("return_url")

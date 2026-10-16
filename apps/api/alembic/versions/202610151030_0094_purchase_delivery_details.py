"""Optional purchase delivery name for branch capture.

Revision ID: 0094_purchase_delivery_details
Revises: 0093_whatsapp_order_channel
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0094_purchase_delivery_details"
down_revision: str | None = "0093_whatsapp_order_channel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("purchase_documents") as batch:
        batch.add_column(sa.Column("delivered_by_name", sa.String(160), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    has_history = bind.execute(
        sa.text(
            "SELECT 1 FROM purchase_documents "
            "WHERE delivered_by_name IS NOT NULL LIMIT 1"
        )
    ).first()
    if has_history:
        raise RuntimeError("0094 downgrade blocked: purchase delivery names exist")
    with op.batch_alter_table("purchase_documents") as batch:
        batch.drop_column("delivered_by_name")

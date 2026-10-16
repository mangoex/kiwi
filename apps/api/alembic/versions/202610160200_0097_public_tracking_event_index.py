"""Index bounded public tracking event reads.

Revision ID: 0097_public_tracking_event_index
Revises: 0096_driver_cash_settlements
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0097_public_tracking_event_index"
down_revision: str | None = "0096_driver_cash_settlements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_order_events_tracking", "order_events", ["order_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_events_tracking", table_name="order_events")

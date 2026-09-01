"""Add google_review_url to branches and create customer_feedbacks table.

Revision ID: 0061_add_branches_google_review_url
Revises: 0060_update_orders_channel_check_constraint
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0061_add_branches_google_review_url"
down_revision: str | None = "0060_update_orders_channel_check_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add google_review_url to branches
    op.add_column("branches", sa.Column("google_review_url", sa.String(500), nullable=True))

    # 2. Create customer_feedbacks table
    op.create_table(
        "customer_feedbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("order_folio", sa.String(64), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(160), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customer_feedbacks_branch_created", "customer_feedbacks", ["branch_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_customer_feedbacks_branch_created", table_name="customer_feedbacks")
    op.drop_table("customer_feedbacks")
    op.drop_column("branches", "google_review_url")

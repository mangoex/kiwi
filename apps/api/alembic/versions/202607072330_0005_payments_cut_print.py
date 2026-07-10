from __future__ import annotations

# ruff: noqa: E501
"""payments cut print

Revision ID: 202607072330
Revises: 202607072200
Create Date: 2026-07-07 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607072330"
down_revision: str | None = "202607072200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.String(length=36),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "cash_shift_id",
            sa.String(length=36),
            sa.ForeignKey("cash_shifts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_order_status", "payments", ["order_id", "status"])
    op.create_table(
        "cash_shift_cuts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "cash_shift_id",
            sa.String(length=36),
            sa.ForeignKey("cash_shifts.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("sales_total_cents", sa.Integer(), nullable=False),
        sa.Column("payment_total_cents", sa.Integer(), nullable=False),
        sa.Column("cash_payment_total_cents", sa.Integer(), nullable=False),
        sa.Column("opening_cash_cents", sa.Integer(), nullable=False),
        sa.Column("expected_cash_cents", sa.Integer(), nullable=False),
        sa.Column("counted_cash_cents", sa.Integer(), nullable=False),
        sa.Column("difference_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.String(length=36),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_print_jobs_status", "print_jobs", ["branch_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_print_jobs_status", table_name="print_jobs")
    op.drop_table("print_jobs")
    op.drop_table("cash_shift_cuts")
    op.drop_index("ix_payments_order_status", table_name="payments")
    op.drop_table("payments")

"""add reconciliation audit logs table

Revision ID: 0043_reconciliation_audit_log
Revises: 0042_sec001_operational
"""

from alembic import op
import sqlalchemy as sa

revision = "0043_reconciliation_audit_log"
down_revision = "0042_sec001_operational"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("audited_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("audited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("branch_id", "date", name="uq_reconciliation_audit_logs_branch_date"),
    )
    op.create_index(
        "ix_reconciliation_audit_org_branch_date",
        "reconciliation_audit_logs",
        ["organization_id", "branch_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_reconciliation_audit_org_branch_date", table_name="reconciliation_audit_logs")
    op.drop_table("reconciliation_audit_logs")

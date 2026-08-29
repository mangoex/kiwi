"""Persist bounded Admin AI proposal lifecycle.

Revision ID: 0055_admin_ai_proposals
Revises: 0054_seed_standard_cash_movement_concepts
"""

from alembic import op
import sqlalchemy as sa

revision = "0055_admin_ai_proposals"
down_revision = "0054_seed_standard_cash_movement_concepts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_ai_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id")),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("base_fingerprint", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("apply_idempotency_key", sa.String(180), unique=True),
        sa.Column("result", sa.JSON()),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'READY_FOR_REVIEW', 'APPLIED', 'REJECTED', 'EXPIRED')",
            name="ck_admin_ai_proposals_status",
        ),
    )
    op.create_index(
        "ix_admin_ai_proposals_org_status", "admin_ai_proposals", ["organization_id", "status"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM admin_ai_proposals LIMIT 1")).first():
        raise RuntimeError("admin AI proposal history blocks downgrade")
    op.drop_index("ix_admin_ai_proposals_org_status", table_name="admin_ai_proposals")
    op.drop_table("admin_ai_proposals")

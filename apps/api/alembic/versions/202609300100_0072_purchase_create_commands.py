"""SR-WORKSPACE-001 durable purchase creation results."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0072_purchase_create_commands"
down_revision = "0071_classification_rollout"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_create_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "purchase_id", sa.String(36), sa.ForeignKey("purchase_documents.id"), nullable=False
        ),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_purchase_create_org_key"
        ),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM purchase_create_commands LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade 0072 while purchase creation history exists")
    op.drop_table("purchase_create_commands")

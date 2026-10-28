"""PUR-DRAFT-001 versioned, replay-safe edits for pending purchases."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0104_purchase_draft_edits"
down_revision = "0103_blind_cash_phases_2_6"
branch_labels = depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("purchase_documents") as batch:
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_purchase_documents_version", "version >= 1")
    op.create_table(
        "purchase_update_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purchase_id", sa.String(36), sa.ForeignKey("purchase_documents.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_purchase_update_org_key"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM purchase_update_commands LIMIT 1")).first():
        raise RuntimeError("0104 downgrade blocked: purchase edit receipts exist")
    if bind.execute(sa.text("SELECT 1 FROM purchase_documents WHERE version > 1 LIMIT 1")).first():
        raise RuntimeError("0104 downgrade blocked: edited purchase drafts exist")
    op.drop_table("purchase_update_commands")
    with op.batch_alter_table("purchase_documents") as batch:
        batch.drop_constraint("ck_purchase_documents_version", type_="check")
        batch.drop_column("version")

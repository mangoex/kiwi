"""add PCO-007 recipe version commands and report indexes

Revision ID: 0042_recipe_reports
Revises: 0041_user_cash_cuts
"""

from alembic import op
import sqlalchemy as sa

revision = "0042_recipe_reports"
down_revision = "0041_user_cash_cuts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_version_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id")),
        sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_recipe_version_commands_key"),
        sa.CheckConstraint("trim(idempotency_key) != ''", name="ck_recipe_version_commands_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_recipe_version_commands_hash"),
    )
    op.create_index("ix_pco007_purchase_report", "purchase_documents", ["organization_id", "branch_id", "confirmed_at"])
    op.create_index("ix_pco007_purchase_cancelled_report", "purchase_documents", ["organization_id", "branch_id", "cancelled_at"])
    op.create_index("ix_pco007_cash_report", "cash_movements", ["organization_id", "branch_id", "created_at"])
    op.create_index("ix_pco007_recipe_snapshot", "order_line_consumption_snapshots", ["order_id", "recipe_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM recipe_version_commands LIMIT 1")).first():
        raise RuntimeError("PCO-007 history blocks downgrade; recipe commands are append-only")
    op.drop_index("ix_pco007_recipe_snapshot", table_name="order_line_consumption_snapshots")
    op.drop_index("ix_pco007_cash_report", table_name="cash_movements")
    op.drop_index("ix_pco007_purchase_cancelled_report", table_name="purchase_documents")
    op.drop_index("ix_pco007_purchase_report", table_name="purchase_documents")
    op.drop_table("recipe_version_commands")

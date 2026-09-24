"""Add explicit commercial classification without inferring legacy values."""
import sqlalchemy as sa
from alembic import op

revision = "0070_catalog_classification"
down_revision = "0069_selectable_compound_product"
branch_labels = depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("product_categories") as batch:
        batch.add_column(sa.Column("classification_code", sa.String(16), nullable=True))
        batch.add_column(sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_category_classification", "classification_code IN ('food', 'drinks', 'other')")
        batch.create_check_constraint("ck_category_configuration_version", "configuration_version > 0")
    op.create_table(
        "category_configuration_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "actor_user_id", "operation", "idempotency_key", name="uq_category_configuration_command"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM category_configuration_commands LIMIT 1")).first() or connection.execute(sa.text("SELECT 1 FROM product_categories WHERE classification_code IS NOT NULL OR configuration_version <> 1 LIMIT 1")).first():
        raise RuntimeError("Classification history exists; revert catalog mode instead of dropping history")
    op.drop_table("category_configuration_commands")
    with op.batch_alter_table("product_categories") as batch:
        batch.drop_constraint("ck_category_configuration_version", type_="check")
        batch.drop_constraint("ck_category_classification", type_="check")
        batch.drop_column("configuration_version")
        batch.drop_column("classification_code")

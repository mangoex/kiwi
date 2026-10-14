"""Durable preparation without enabling external fiscal dispatch."""

import sqlalchemy as sa
from alembic import op
from restaurant_os.fiscal_command_schema import ORDER_SCOPE_INDEX, tables

revision = "0087_fiscal_commands"
down_revision = "0086_fiscal_emitters"
branch_labels = depends_on = None


def _tables():
    metadata = sa.MetaData()
    for name in ("organizations", "users"):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True))
    for name in ("branches", "legal_entities"):
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
        )
    sa.Table(
        "orders",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "fiscal_emitter_configuration_versions",
        metadata,
        sa.Column("configuration_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    return tables(metadata)


def upgrade() -> None:
    bind = op.get_bind()
    op.create_index(
        ORDER_SCOPE_INDEX, "orders", ["id", "organization_id", "branch_id"], unique=True
    )
    for table in _tables():
        table.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if any(
        bind.execute(sa.text(f"SELECT 1 FROM {table.name} LIMIT 1")).first() for table in _tables()
    ):
        raise RuntimeError("0087 downgrade blocked: fiscal intention history exists")
    for table in reversed(_tables()):
        table.drop(bind)
    op.drop_index(ORDER_SCOPE_INDEX, table_name="orders")

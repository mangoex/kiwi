"""Versioned delivery tariffs, policies and immutable monetary snapshots."""
import sqlalchemy as sa
from alembic import op

revision = "0100_delivery_fee"
down_revision = "0099_mobile_password_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from restaurant_os.delivery_fee_schema import tables

    metadata = sa.MetaData()
    for name in ("organizations", "users", "branches", "orders", "payments"):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True))
    for table in tables(metadata):
        table.create(op.get_bind())


def downgrade() -> None:
    from restaurant_os.delivery_fee_schema import tables

    names = [table.name for table in tables(sa.MetaData())]
    for name in names:
        if op.get_bind().scalar(sa.text(f"SELECT COUNT(*) FROM {name}")):
            raise RuntimeError("Delivery history exists; preserve it before downgrade")
    for name in reversed(names):
        op.drop_table(name)

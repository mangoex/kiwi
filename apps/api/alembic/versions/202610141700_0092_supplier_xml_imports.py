"""Private supplier originals without automatic inventory or payable effects."""

import sqlalchemy as sa
from alembic import op
from restaurant_os.supplier_xml_schema import tables

revision = "0092_supplier_xml_imports"
down_revision = "0091_cash_lifecycle_intents"
branch_labels = depends_on = None


def _tables():
    metadata = sa.MetaData()
    for name in ("users", "branches", "legal_entities"):
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
        )
    return tables(metadata)


def upgrade() -> None:
    for table in _tables():
        table.create(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    items = _tables()
    if any(bind.execute(sa.select(table.c.id).limit(1)).first() for table in items):
        raise RuntimeError("0092 downgrade blocked: supplier document evidence exists")
    for table in reversed(items):
        table.drop(bind)

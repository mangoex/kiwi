"""Verified mobile identities and optional CRM birthday; preserve historical rows."""
from alembic import op
import sqlalchemy as sa

revision = "0098_mobile_customer_profile"
down_revision = "0097_public_tracking_event_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from restaurant_os.mobile_customer_schema import mobile_tables

    for name in ("birthday_day", "birthday_month", "birthday_year"):
        op.add_column("customers", sa.Column(name, sa.Integer(), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        # Preserve the table referenced by historical orders instead of batch recreation.
        op.execute("ALTER TABLE public_order_intents ADD COLUMN customer_id VARCHAR(36) REFERENCES customers(id)")
    else:
        op.add_column("public_order_intents", sa.Column("customer_id", sa.String(36), nullable=True))
        op.create_foreign_key("fk_mobile_intent_customer", "public_order_intents", "customers", ["customer_id"], ["id"])
    metadata = sa.MetaData()
    for name in ("organizations", "branches", "customers"):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True))
    for table in mobile_tables(metadata):
        table.create(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    for query in (
        "SELECT COUNT(*) FROM mobile_customer_identities",
        "SELECT COUNT(*) FROM mobile_access_challenges",
        "SELECT COUNT(*) FROM mobile_customer_sessions",
        "SELECT COUNT(*) FROM customers WHERE birthday_day IS NOT NULL OR birthday_month IS NOT NULL OR birthday_year IS NOT NULL",
        "SELECT COUNT(*) FROM public_order_intents WHERE customer_id IS NOT NULL",
    ):
        if connection.scalar(sa.text(query)):
            raise RuntimeError("Mobile profile data exists; preserve it before downgrade")
    for name in ("mobile_customer_sessions", "mobile_access_challenges", "mobile_customer_identities"):
        op.drop_table(name)
    if connection.dialect.name != "sqlite":
        op.drop_constraint("fk_mobile_intent_customer", "public_order_intents", type_="foreignkey")
    op.drop_column("public_order_intents", "customer_id")
    for name in ("birthday_year", "birthday_month", "birthday_day"):
        op.drop_column("customers", name)

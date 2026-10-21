"""Password access without an SMS provider; preserve legacy verified identities."""

import sqlalchemy as sa
from alembic import op

revision = "0099_mobile_password_access"
down_revision = "0098_mobile_customer_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from restaurant_os.mobile_password_schema import password_tables

    metadata = sa.MetaData()
    sa.Table("mobile_customer_identities", metadata,
             sa.Column("id", sa.String(36), primary_key=True))
    for table in password_tables(metadata):
        table.create(op.get_bind())


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM mobile_customer_credentials")):
        raise RuntimeError("Mobile credentials exist; preserve them before downgrade")
    op.drop_table("mobile_auth_attempts")
    op.drop_table("mobile_customer_credentials")

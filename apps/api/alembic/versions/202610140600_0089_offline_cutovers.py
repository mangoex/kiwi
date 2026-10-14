"""A cutover receipt is explicit evidence, never readiness created by migration."""

import sqlalchemy as sa
from alembic import op
from restaurant_os.offline_cutover_schema import table

revision = "0089_offline_cutovers"
down_revision = "0088_offline_authorization"
branch_labels = depends_on = None


def _table():
    metadata = sa.MetaData()
    sa.Table("organizations", metadata, sa.Column("id", sa.String(36), primary_key=True))
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36)),
    )
    return table(metadata)


def upgrade() -> None:
    _table().create(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    cutovers = _table()
    if bind.scalar(sa.select(sa.func.count()).select_from(cutovers)):
        raise RuntimeError("0089 downgrade blocked: offline cutover evidence exists")
    cutovers.drop(bind)

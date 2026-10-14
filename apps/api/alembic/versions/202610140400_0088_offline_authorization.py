"""Shared offline authority registry; migration is not evidence of writer cutover."""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from restaurant_os.offline_authorization_schema import USER_SCOPE_INDEX, tables

revision = "0088_offline_authorization"
down_revision = "0087_fiscal_commands"
branch_labels = depends_on = None


def _tables():
    metadata = sa.MetaData()
    for name in (
        "organizations",
        "device_credentials",
        "offline_order_bundles",
        "offline_order_grants",
    ):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True))
    for name in ("users", "branches"):
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
        )
    return tables(metadata)


def upgrade() -> None:
    bind = op.get_bind()
    op.create_index(USER_SCOPE_INDEX, "users", ["organization_id", "id"], unique=True)
    rollouts, leases = _tables()
    rollouts.create(bind)
    leases.create(bind)
    now = datetime.now(timezone.utc)
    organization_ids = bind.scalars(sa.text("SELECT id FROM organizations")).all()
    if organization_ids:
        bind.execute(
            rollouts.insert(),
            [
                {"organization_id": organization_id, "state": "unprepared", "created_at": now}
                for organization_id in organization_ids
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()
    rollouts, leases = _tables()
    if bind.scalar(sa.select(sa.func.count()).select_from(leases)) or bind.scalar(
        sa.select(sa.func.count()).select_from(rollouts).where(rollouts.c.state != "unprepared")
    ):
        raise RuntimeError("0088 downgrade blocked: offline authorization evidence exists")
    leases.drop(bind)
    rollouts.drop(bind)
    op.drop_index(USER_SCOPE_INDEX, table_name="users")

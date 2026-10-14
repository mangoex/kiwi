"""Record central intent before financial execution; retain all recovery history."""

import sqlalchemy as sa
from alembic import op
from restaurant_os.operational_intent_schema import WORKSPACE_SCOPE_INDEX, table

revision = "0090_operational_intents"
down_revision = "0089_offline_cutovers"
branch_labels = depends_on = None


def _table():
    metadata = sa.MetaData()
    sa.Table(
        "branch_workspace_sessions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36)),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("branch_id", sa.String(36)),
    )
    return table(metadata)


def upgrade() -> None:
    op.create_index(
        WORKSPACE_SCOPE_INDEX,
        "branch_workspace_sessions",
        ["organization_id", "actor_user_id", "branch_id", "id"],
        unique=True,
    )
    _table().create(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    intents = _table()
    if bind.scalar(sa.select(sa.func.count()).select_from(intents)):
        raise RuntimeError("0090 downgrade blocked: operational command history exists")
    intents.drop(bind)
    op.drop_index(WORKSPACE_SCOPE_INDEX, table_name="branch_workspace_sessions")

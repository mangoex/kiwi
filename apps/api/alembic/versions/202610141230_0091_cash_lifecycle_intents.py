"""Extend durable intents with cash lifecycle and domain-key namespaces."""

import sqlalchemy as sa
from alembic import op
from restaurant_os.operational_intent_schema import CASH_LIFECYCLE_KINDS, lifecycle_checks, table

revision = "0091_cash_lifecycle_intents"
down_revision = "0090_operational_intents"
branch_labels = depends_on = None
NAME = "operational_command_intents"


def upgrade() -> None:
    checks = lifecycle_checks()
    op.add_column(NAME, sa.Column("command_namespace", sa.String(32), nullable=True))
    op.execute(
        sa.text(
            "UPDATE operational_command_intents SET command_namespace = "
            "CASE WHEN kind = 'cash.movement.create' THEN 'cash.movement' ELSE kind END"
        )
    )
    with op.batch_alter_table(NAME) as batch:
        batch.alter_column("command_namespace", existing_type=sa.String(32), nullable=False)
        for key in ("kind", "target", "key"):
            batch.drop_constraint(f"ck_operational_intent_{key}", type_="check")
            batch.create_check_constraint(f"ck_operational_intent_{key}", checks[key])
        batch.create_check_constraint("ck_operational_intent_namespace", checks["namespace"])
        batch.create_unique_constraint(
            "uq_operational_intent_namespace_key",
            ["organization_id", "command_namespace", "idempotency_key"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = sa.table(NAME, sa.column("kind"))
    if bind.scalar(
        sa.select(sa.func.count()).select_from(rows).where(rows.c.kind.in_(CASH_LIFECYCLE_KINDS))
    ):
        raise RuntimeError("0091 downgrade blocked: cash lifecycle command history exists")
    legacy_metadata = sa.MetaData()
    # Reading constraint SQL does not create or inspect a foreign workspace table.
    legacy = table(legacy_metadata)
    old_checks = {
        c.name: str(c.sqltext) for c in legacy.constraints if isinstance(c, sa.CheckConstraint)
    }
    with op.batch_alter_table(NAME) as batch:
        batch.drop_constraint("uq_operational_intent_namespace_key", type_="unique")
        batch.drop_constraint("ck_operational_intent_namespace", type_="check")
        for key in ("kind", "target", "key"):
            name = f"ck_operational_intent_{key}"
            batch.drop_constraint(name, type_="check")
            batch.create_check_constraint(name, old_checks[name])
        batch.drop_column("command_namespace")

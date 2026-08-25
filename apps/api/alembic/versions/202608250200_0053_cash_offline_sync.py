"""Add PCO-008 actor binding and serialized branch checkpoints.

Revision ID: 0053_cash_offline_sync
Revises: 0052_pos_handoff_and_idempotency
"""

from alembic import op
import sqlalchemy as sa

revision = "0053_cash_offline_sync"
down_revision = "0052_pos_handoff_and_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_branch_checkpoints",
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            primary_key=True,
        ),
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("branches.id"),
            primary_key=True,
        ),
        sa.Column("last_checkpoint", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_checkpoint >= 0", name="ck_sync_branch_checkpoints_positive"
        ),
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # The legacy SQLite UNIQUE was created inline and is unnamed.  Supply
        # the same deterministic convention used by the approved PCO-008
        # migration so Alembic can address it during table recreation.
        with op.batch_alter_table(
            "sync_commands",
            recreate="always",
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch:
            batch.drop_constraint("uq_sync_commands_idempotency_key", type_="unique")
            batch.add_column(
                sa.Column(
                    "actor_user_id",
                    sa.String(36),
                    sa.ForeignKey("users.id", name="fk_sync_commands_actor_user"),
                    nullable=True,
                )
            )
            batch.add_column(sa.Column("request_hash", sa.String(64), nullable=True))
            batch.create_unique_constraint(
                "uq_sync_commands_org_key", ["organization_id", "idempotency_key"]
            )
            batch.create_unique_constraint(
                "uq_sync_commands_org_command", ["organization_id", "command_id"]
            )
    else:
        legacy = next(
            (
                item.get("name")
                for item in sa.inspect(bind).get_unique_constraints("sync_commands")
                if item.get("column_names") == ["idempotency_key"]
            ),
            None,
        )
        if not legacy:
            raise RuntimeError("sync_commands legacy idempotency unique is required")
        op.drop_constraint(legacy, "sync_commands", type_="unique")
        op.add_column("sync_commands", sa.Column("actor_user_id", sa.String(36)))
        op.add_column("sync_commands", sa.Column("request_hash", sa.String(64)))
        op.create_foreign_key(
            "fk_sync_commands_actor_user",
            "sync_commands",
            "users",
            ["actor_user_id"],
            ["id"],
        )
        op.create_unique_constraint(
            "uq_sync_commands_org_key",
            "sync_commands",
            ["organization_id", "idempotency_key"],
        )
        op.create_unique_constraint(
            "uq_sync_commands_org_command",
            "sync_commands",
            ["organization_id", "command_id"],
        )
    op.create_index(
        "ix_sync_commands_org_branch_checkpoint",
        "sync_commands",
        ["organization_id", "branch_id", "checkpoint"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    protected = (
        "SELECT 1 FROM sync_branch_checkpoints WHERE last_checkpoint > 0 LIMIT 1",
        "SELECT 1 FROM sync_commands WHERE command_type = 'cash.movement.create.v1' LIMIT 1",
    )
    if any(bind.execute(sa.text(query)).first() for query in protected):
        raise RuntimeError("PCO-008 history blocks downgrade")
    op.drop_index("ix_sync_commands_org_branch_checkpoint", table_name="sync_commands")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("sync_commands", recreate="always") as batch:
            batch.drop_constraint("uq_sync_commands_org_command", type_="unique")
            batch.drop_constraint("uq_sync_commands_org_key", type_="unique")
            batch.drop_column("request_hash")
            batch.drop_column("actor_user_id")
            batch.create_unique_constraint(
                "uq_sync_commands_idempotency_key", ["idempotency_key"]
            )
    else:
        op.drop_constraint("uq_sync_commands_org_command", "sync_commands", type_="unique")
        op.drop_constraint("uq_sync_commands_org_key", "sync_commands", type_="unique")
        op.drop_constraint("fk_sync_commands_actor_user", "sync_commands", type_="foreignkey")
        op.drop_column("sync_commands", "request_hash")
        op.drop_column("sync_commands", "actor_user_id")
        op.create_unique_constraint(
            "uq_sync_commands_idempotency_key", "sync_commands", ["idempotency_key"]
        )
    op.drop_table("sync_branch_checkpoints")

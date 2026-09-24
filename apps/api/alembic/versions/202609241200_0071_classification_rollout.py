"""Central classification rollout and installation acknowledgements."""

from alembic import op
import sqlalchemy as sa

revision = "0071_classification_rollout"
down_revision = "0070_catalog_classification"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_classification_rollouts",
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("state", sa.String(16), nullable=False, server_default="legacy"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prepared_fingerprint", sa.String(64), nullable=True),
        sa.Column("online_readiness", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('legacy','preparing','adopting','explicit','reverting')",
            name="ck_class_rollout_state",
        ),
        sa.CheckConstraint("version >= 0", name="ck_class_rollout_version"),
    )

    op.create_table(
        "catalog_classification_branches",
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("rollout_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issued_hash", sa.String(64), nullable=True),
        sa.Column("issued_mode", sa.String(16), nullable=False, server_default="legacy"),
        sa.Column("confirmed_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_hash", sa.String(64), nullable=True),
        sa.Column("confirmed_mode", sa.String(16), nullable=False, server_default="legacy"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "generation >= 0 AND confirmed_generation >= 0", name="ck_class_branch_generation"
        ),
        sa.CheckConstraint(
            "issued_mode IN ('legacy','explicit') AND confirmed_mode IN ('legacy','explicit')",
            name="ck_class_branch_mode",
        ),
    )

    op.create_table(
        "catalog_classification_rollout_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "actor_id", "idempotency_key", name="uq_class_rollout_command"
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for name in (
        "catalog_classification_rollouts",
        "catalog_classification_branches",
        "catalog_classification_rollout_commands",
    ):
        if connection.scalar(sa.text(f"SELECT COUNT(*) FROM {name}")):
            raise RuntimeError("classification_rollout_history_prevents_downgrade")
    op.drop_table("catalog_classification_rollout_commands")
    op.drop_table("catalog_classification_branches")
    op.drop_table("catalog_classification_rollouts")

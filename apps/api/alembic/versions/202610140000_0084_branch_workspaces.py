"""Add durable branch contexts; preserve command and audit history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0084_branch_workspaces"
down_revision: str | None = "0083_corporate_allocation_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("branch_selection_commands") as batch:
        batch.alter_column("source_branch_id", existing_type=sa.String(36), nullable=True)
    op.create_table(
        "branch_workspace_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("authorization_version", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("secret_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column(
            "selection_command_id", sa.String(36), sa.ForeignKey("branch_selection_commands.id")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "authorization_version >= 1", name="ck_branch_workspace_authority_version"
        ),
        sa.CheckConstraint("secret_version >= 1", name="ck_branch_workspace_secret_version"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_branch_workspace_token_hash"),
        sa.CheckConstraint(
            "state IN ('active', 'recovery_only', 'superseded', 'revoked', 'expired')",
            name="ck_branch_workspace_state",
        ),
    )
    op.create_index(
        "uq_branch_workspace_operational_actor",
        "branch_workspace_sessions",
        ["organization_id", "actor_user_id"],
        unique=True,
        sqlite_where=sa.text("state IN ('active', 'recovery_only')"),
        postgresql_where=sa.text("state IN ('active', 'recovery_only')"),
    )
    op.create_table(
        "branch_context_reissue_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "context_id",
            sa.String(36),
            sa.ForeignKey("branch_workspace_sessions.id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("authorization_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "idempotency_key",
            name="uq_branch_context_reissue_actor_key",
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_branch_context_reissue_hash"),
        sa.CheckConstraint("trim(idempotency_key) != ''", name="ck_branch_context_reissue_key"),
        sa.CheckConstraint("authorization_version >= 1", name="ck_branch_context_reissue_version"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "branch_workspace_sessions",
        "branch_context_reissue_commands",
        "branch_selection_commands",
    ):
        if connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}")):
            raise RuntimeError("Cannot downgrade 0084 while workspace or selection history exists")
    op.drop_table("branch_context_reissue_commands")
    op.drop_table("branch_workspace_sessions")
    with op.batch_alter_table("branch_selection_commands") as batch:
        batch.alter_column("source_branch_id", existing_type=sa.String(36), nullable=False)

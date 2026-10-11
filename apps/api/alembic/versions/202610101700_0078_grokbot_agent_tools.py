"""Add governed GrokBot Agent Tools identities, commands and provenance.

Revision ID: 0078_grokbot_agent_tools
Revises: 0077_pos_branch_selection
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0078_grokbot_agent_tools"
down_revision: str | None = "0077_pos_branch_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_agent_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="GROKBOT"),
        sa.Column(
            "display_name", sa.String(120), nullable=False, server_default="Administrador Kiwi"
        ),
        sa.Column("base_url", sa.String(600)),
        sa.Column("callback_url", sa.String(600)),
        sa.Column("callback_key_id", sa.String(64)),
        sa.Column("callback_secret_ref", sa.String(240)),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("state", sa.String(24), nullable=False, server_default="DISCONNECTED"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "provider", name="uq_external_agent_integrations_org_provider"
        ),
        sa.CheckConstraint(
            "state IN ('DISCONNECTED','CONNECTED','DEGRADED','DRAINING','PAUSED')",
            name="ck_external_agent_integrations_state",
        ),
    )
    op.create_table(
        "external_agent_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column(
            "integration_id",
            sa.String(36),
            sa.ForeignKey("external_agent_integrations.id"),
            nullable=False,
        ),
        sa.Column("profile", sa.String(24), nullable=False),
        sa.Column("client_id", sa.String(128), unique=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("corporate_scope", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("authorization_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "integration_id", "profile", name="uq_external_agent_identities_profile"
        ),
        sa.CheckConstraint(
            "profile IN ('administrator','kitchen','inventory','purchasing')",
            name="ck_external_agent_identities_profile",
        ),
        sa.CheckConstraint(
            "authorization_version > 0", name="ck_external_agent_identities_auth_version"
        ),
    )
    op.create_table(
        "external_agent_identity_branches",
        sa.Column(
            "identity_id",
            sa.String(36),
            sa.ForeignKey("external_agent_identities.id"),
            primary_key=True,
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "external_agent_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "identity_id",
            sa.String(36),
            sa.ForeignKey("external_agent_identities.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("secret_salt", sa.String(64), nullable=False),
        sa.Column("secret_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "identity_id", "version", name="uq_external_agent_credentials_identity_version"
        ),
    )
    op.create_table(
        "external_agent_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column(
            "integration_id",
            sa.String(36),
            sa.ForeignKey("external_agent_integrations.id"),
            nullable=False,
        ),
        sa.Column(
            "identity_id",
            sa.String(36),
            sa.ForeignKey("external_agent_identities.id"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id")),
        sa.Column("operation_type", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("reason_code", sa.String(64)),
        sa.Column("correlation_id", sa.String(100)),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "identity_id",
            "idempotency_key",
            name="uq_external_agent_commands_identity_key",
        ),
        sa.CheckConstraint(
            "operation_type IN ('catalog_proposal','inventory_item_proposal',"
            "'recipe_proposal','purchase_draft')",
            name="ck_external_agent_commands_type",
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED','VALIDATED','READY_FOR_REVIEW','DRAFT_CREATED','REJECTED',"
            "'APPLIED','EXPIRED','CONFIRMED_BY_HUMAN','CANCELLED_BY_HUMAN')",
            name="ck_external_agent_commands_status",
        ),
    )
    op.create_table(
        "external_agent_callback_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("external_agent_commands.id"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("destination", sa.String(600), nullable=False),
        sa.Column("key_id", sa.String(64)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("leased_until", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','DELIVERING','DELIVERED','EXHAUSTED')",
            name="ck_external_agent_callback_outbox_status",
        ),
    )

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("actor_agent_identity_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_audit_events_actor_agent_identity",
            "external_agent_identities",
            ["actor_agent_identity_id"],
            ["id"],
        )
    with op.batch_alter_table("admin_ai_proposals") as batch:
        batch.alter_column("actor_user_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("actor_agent_identity_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("origin", sa.String(24), nullable=False, server_default="HUMAN"))
        batch.create_foreign_key(
            "fk_admin_ai_proposals_actor_agent_identity",
            "external_agent_identities",
            ["actor_agent_identity_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_admin_ai_proposals_actor_origin",
            "(actor_user_id IS NOT NULL AND actor_agent_identity_id IS NULL AND origin = 'HUMAN') "
            "OR (actor_user_id IS NULL AND actor_agent_identity_id IS NOT NULL "
            "AND origin = 'GROKBOT')",
        )
    with op.batch_alter_table("purchase_documents") as batch:
        batch.alter_column("created_by", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("created_by_agent_identity_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("origin", sa.String(24), nullable=False, server_default="HUMAN"))
        batch.create_foreign_key(
            "fk_purchase_documents_created_by_agent_identity",
            "external_agent_identities",
            ["created_by_agent_identity_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_purchase_documents_creator_origin",
            "(created_by IS NOT NULL AND created_by_agent_identity_id IS NULL "
            "AND origin = 'HUMAN') OR (created_by IS NULL "
            "AND created_by_agent_identity_id IS NOT NULL AND origin = 'GROKBOT')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM external_agent_commands LIMIT 1")).first():
        raise RuntimeError("0078 downgrade blocked: external agent command history exists")
    if (
        bind.execute(
            sa.text(
                "SELECT 1 FROM admin_ai_proposals WHERE actor_agent_identity_id IS NOT NULL LIMIT 1"
            )
        ).first()
        or bind.execute(
            sa.text(
                "SELECT 1 FROM purchase_documents "
                "WHERE created_by_agent_identity_id IS NOT NULL LIMIT 1"
            )
        ).first()
    ):
        raise RuntimeError("0078 downgrade blocked: agent-created domain history exists")

    with op.batch_alter_table("purchase_documents") as batch:
        batch.drop_constraint("ck_purchase_documents_creator_origin", type_="check")
        batch.drop_constraint("fk_purchase_documents_created_by_agent_identity", type_="foreignkey")
        batch.drop_column("origin")
        batch.drop_column("created_by_agent_identity_id")
        batch.alter_column("created_by", existing_type=sa.String(36), nullable=False)
    with op.batch_alter_table("admin_ai_proposals") as batch:
        batch.drop_constraint("ck_admin_ai_proposals_actor_origin", type_="check")
        batch.drop_constraint("fk_admin_ai_proposals_actor_agent_identity", type_="foreignkey")
        batch.drop_column("origin")
        batch.drop_column("actor_agent_identity_id")
        batch.alter_column("actor_user_id", existing_type=sa.String(36), nullable=False)
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("fk_audit_events_actor_agent_identity", type_="foreignkey")
        batch.drop_column("actor_agent_identity_id")

    op.drop_table("external_agent_callback_outbox")
    op.drop_table("external_agent_commands")
    op.drop_table("external_agent_credentials")
    op.drop_table("external_agent_identity_branches")
    op.drop_table("external_agent_identities")
    op.drop_table("external_agent_integrations")

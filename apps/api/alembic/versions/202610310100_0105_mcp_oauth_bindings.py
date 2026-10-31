"""MCP-001 provider-neutral OAuth bindings for external agent identities."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0105_mcp_oauth_bindings"
down_revision = "0104_purchase_draft_edits"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_agent_oauth_bindings",
        sa.Column(
            "identity_id",
            sa.String(36),
            sa.ForeignKey("external_agent_identities.id"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("issuer", sa.String(600), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("oauth_client_id", sa.String(255), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "issuer",
            "subject",
            "oauth_client_id",
            name="uq_external_agent_oauth_bindings_tuple",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM external_agent_oauth_bindings LIMIT 1")).first():
        raise RuntimeError("0105 downgrade blocked: OAuth identity bindings exist")
    op.drop_table("external_agent_oauth_bindings")

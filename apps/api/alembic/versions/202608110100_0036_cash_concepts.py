"""add versioned cash movement concepts without enabling ledger writes

Revision ID: 0036_cash_concepts
Revises: 0035_cumulative_profiles_rbac
Create Date: 2026-08-11 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_cash_concepts"
down_revision: str | None = "0035_cumulative_profiles_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cash_movement_concepts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_cash_concepts_status"),
        sa.UniqueConstraint("organization_id", "code", name="uq_cash_concepts_org_code"),
    )
    op.create_index(
        "ix_cash_concepts_org_status",
        "cash_movement_concepts",
        ["organization_id", "status"],
    )
    op.create_table(
        "cash_movement_concept_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "concept_id",
            sa.String(36),
            sa.ForeignKey("cash_movement_concepts.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("allowed_movement_type", sa.String(16), nullable=False),
        sa.Column("requires_reference", sa.Boolean(), nullable=False),
        sa.Column("requires_evidence", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_cash_concept_versions_positive"),
        sa.CheckConstraint(
            "allowed_movement_type IN ('deposit', 'withdrawal', 'both')",
            name="ck_cash_concept_versions_type",
        ),
        sa.CheckConstraint("requires_reference", name="ck_cash_concept_versions_reference"),
        sa.CheckConstraint("requires_evidence", name="ck_cash_concept_versions_evidence"),
        sa.UniqueConstraint("concept_id", "version", name="uq_cash_concept_versions_number"),
    )
    op.create_index(
        "ix_cash_concept_versions_effective",
        "cash_movement_concept_versions",
        ["concept_id", "valid_from", "version"],
    )
    op.create_table(
        "cash_concept_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "target_concept_id",
            sa.String(36),
            sa.ForeignKey("cash_movement_concepts.id"),
            nullable=False,
        ),
        sa.Column("command_type", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "command_type IN ('create', 'version', 'archive')",
            name="ck_cash_concept_commands_type",
        ),
        sa.CheckConstraint("status = 'completed'", name="ck_cash_concept_commands_status"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_cash_concept_commands_org_key"
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    history_count = sum(
        int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())
        for table_name in (
            "cash_movement_concepts",
            "cash_movement_concept_versions",
            "cash_concept_commands",
        )
    )
    if history_count:
        raise RuntimeError("Safe downgrade blocked: cash concept history exists")
    op.drop_table("cash_concept_commands")
    op.drop_index("ix_cash_concept_versions_effective", table_name="cash_movement_concept_versions")
    op.drop_table("cash_movement_concept_versions")
    op.drop_index("ix_cash_concepts_org_status", table_name="cash_movement_concepts")
    op.drop_table("cash_movement_concepts")

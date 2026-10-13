"""Additive versioned issuer configuration; existing organization config stays intact."""

from __future__ import annotations

import sqlalchemy as sa

LEGAL_ENTITY_INDEX = "uq_legal_entities_organization_id_id"


def tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table]:
    identities = sa.Table(
        "fiscal_emitter_configurations",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("legal_entity_id", sa.String(36), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "legal_entity_id"],
            ["legal_entities.organization_id", "legal_entities.id"],
            name="fk_fiscal_emitter_legal_entity_organization",
        ),
        sa.UniqueConstraint(
            "organization_id", "legal_entity_id", name="uq_fiscal_emitter_org_legal"
        ),
        sa.CheckConstraint("current_version > 0", name="ck_fiscal_emitter_version_positive"),
    )
    versions = sa.Table(
        "fiscal_emitter_configuration_versions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "configuration_id",
            sa.String(36),
            sa.ForeignKey("fiscal_emitter_configurations.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("configuration_id", "version", name="uq_fiscal_emitter_revision"),
        sa.CheckConstraint("version > 0", name="ck_fiscal_emitter_revision_positive"),
    )
    return identities, versions

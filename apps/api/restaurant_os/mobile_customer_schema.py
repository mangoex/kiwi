"""Additive schema shared by metadata and migration 0098."""

from __future__ import annotations

import sqlalchemy as sa


def mobile_tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table, sa.Table]:
    identities = sa.Table(
        "mobile_customer_identities",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "phone", name="uq_mobile_identity_phone"),
    )
    challenges = sa.Table(
        "mobile_access_challenges",
        metadata,
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("verification_id", sa.String(64), nullable=False),
        sa.Column("identity_id", sa.String(36), sa.ForeignKey(identities.c.id)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    sessions = sa.Table(
        "mobile_customer_sessions",
        metadata,
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("identity_id", sa.String(36), sa.ForeignKey(identities.c.id), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    return identities, challenges, sessions

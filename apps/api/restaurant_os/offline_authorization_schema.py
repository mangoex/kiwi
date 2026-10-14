"""Shared offline authority evidence; never persist another copy of signed grants."""

from __future__ import annotations

import sqlalchemy as sa

USER_SCOPE_INDEX = "uq_users_offline_organization_identity"


def tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table]:
    rollouts = sa.Table(
        "offline_authorization_rollouts",
        metadata,
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("registration_started_at", sa.DateTime(timezone=True)),
        sa.Column("legacy_drain_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('unprepared','draining','clean_install')",
            name="ck_offline_auth_rollout_state",
        ),
        sa.CheckConstraint(
            "(state = 'unprepared' AND registration_started_at IS NULL "
            "AND legacy_drain_until IS NULL) "
            "OR (state IN ('draining','clean_install') AND registration_started_at IS NOT NULL "
            "AND legacy_drain_until IS NOT NULL AND legacy_drain_until >= registration_started_at)",
            name="ck_offline_auth_rollout_evidence",
        ),
    )
    leases = sa.Table(
        "offline_authorization_leases",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("grant_kind", sa.String(16), nullable=False),
        sa.Column("grant_hash", sa.String(64), nullable=False),
        sa.Column("authorization_version", sa.Integer()),
        sa.Column("provenance", sa.String(24), nullable=False),
        sa.Column(
            "source_device_id",
            sa.String(36),
            sa.ForeignKey("device_credentials.id"),
            nullable=False,
        ),
        sa.Column("bundle_id", sa.String(36), sa.ForeignKey("offline_order_bundles.id")),
        sa.Column("source_grant_id", sa.String(36), sa.ForeignKey("offline_order_grants.id")),
        sa.Column("lease_epoch", sa.Integer()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_offline_auth_actor_scope",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["branches.organization_id", "branches.id"],
            name="fk_offline_auth_branch_scope",
        ),
        sa.UniqueConstraint(
            "organization_id", "grant_kind", "grant_hash", name="uq_offline_auth_grant_identity"
        ),
        sa.UniqueConstraint(
            "organization_id", "source_grant_id", name="uq_offline_auth_source_grant"
        ),
        sa.CheckConstraint("grant_kind IN ('cash','orders')", name="ck_offline_auth_kind"),
        sa.CheckConstraint("length(grant_hash) = 64", name="ck_offline_auth_hash"),
        sa.CheckConstraint(
            "(provenance = 'registered' AND authorization_version IS NOT NULL "
            "AND authorization_version >= 1) OR "
            "(provenance = 'retained_legacy' AND authorization_version IS NULL)",
            name="ck_offline_auth_version_provenance",
        ),
        sa.CheckConstraint("expires_at >= issued_at", name="ck_offline_auth_interval"),
        sa.CheckConstraint("state IN ('active','revoked','expired')", name="ck_offline_auth_state"),
        sa.CheckConstraint(
            "(grant_kind = 'cash' AND bundle_id IS NULL AND lease_epoch IS NULL "
            "AND source_grant_id IS NULL) OR "
            "(grant_kind = 'orders' AND bundle_id IS NOT NULL AND lease_epoch IS NOT NULL "
            "AND lease_epoch > 0 AND source_grant_id IS NOT NULL)",
            name="ck_offline_auth_domain_binding",
        ),
        sa.CheckConstraint(
            "(state = 'revoked' AND revoked_at IS NOT NULL) OR "
            "(state != 'revoked' AND revoked_at IS NULL)",
            name="ck_offline_auth_revocation",
        ),
        sa.Index("ix_offline_auth_actor_expiry", "organization_id", "actor_user_id", "expires_at"),
    )
    return rollouts, leases

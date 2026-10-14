"""Immutable identity of an operator-confirmed offline issuer cutover."""

import sqlalchemy as sa


def table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "offline_authorization_cutovers",
        metadata,
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("retirement_evidence_sha256", sa.String(64), nullable=False),
        sa.Column("registration_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("legacy_drain_until", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_offline_cutover_actor_scope",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64 AND length(request_hash) = 64 "
            "AND length(retirement_evidence_sha256) = 64",
            name="ck_offline_cutover_hashes",
        ),
        sa.CheckConstraint(
            "legacy_drain_until >= registration_started_at",
            name="ck_offline_cutover_interval",
        ),
    )

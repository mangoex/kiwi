"""Scope-bound identity and evidence of a central command, without its body."""

import sqlalchemy as sa

WORKSPACE_SCOPE_INDEX = "uq_operational_workspace_scope"


def table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "operational_command_intents",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("context_id", sa.String(36), nullable=False),
        sa.Column("authorization_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(36)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("domain_command_id", sa.String(36)),
        sa.Column("domain_request_hash", sa.String(64)),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id", "branch_id", "context_id"],
            [
                "branch_workspace_sessions.organization_id",
                "branch_workspace_sessions.actor_user_id",
                "branch_workspace_sessions.branch_id",
                "branch_workspace_sessions.id",
            ],
            name="fk_operational_intent_workspace_scope",
        ),
        sa.UniqueConstraint(
            "organization_id", "kind", "idempotency_key", name="uq_operational_intent_kind_key"
        ),
        sa.CheckConstraint(
            "authorization_version >= 1 AND length(request_hash) = 64",
            name="ck_operational_intent_identity",
        ),
        sa.CheckConstraint(
            "(kind = 'cash.movement.create' AND length(idempotency_key) BETWEEN 1 AND 180) OR "
            "(kind <> 'cash.movement.create' AND length(idempotency_key) BETWEEN 12 AND 160)",
            name="ck_operational_intent_key",
        ),
        sa.CheckConstraint(
            "kind IN ('order.create', 'payment.confirm', 'cash.movement.create')",
            name="ck_operational_intent_kind",
        ),
        sa.CheckConstraint(
            "(kind = 'payment.confirm' AND target_id IS NOT NULL) OR "
            "(kind <> 'payment.confirm' AND target_id IS NULL)",
            name="ck_operational_intent_target",
        ),
        sa.CheckConstraint(
            "(state IN ('prepared', 'no_effect') AND domain_command_id IS NULL "
            "AND domain_request_hash IS NULL AND resource_id IS NULL) OR "
            "(state IN ('applied', 'acknowledged') AND domain_command_id IS NOT NULL "
            "AND length(domain_request_hash) = 64 AND resource_id IS NOT NULL)",
            name="ck_operational_intent_evidence",
        ),
        sa.Index("ix_operational_intent_actor_state", "organization_id", "actor_user_id", "state"),
    )

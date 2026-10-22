"""CORTE-CIEGO-001: additive, organization-bound authority evidence."""

from __future__ import annotations

import sqlalchemy as sa

DATASETS = ("cash.shifts", "cash.cuts", "cash.movements", "sales", "reconciliation", "expenses")
CAPABILITIES = (
    "cash.user_cut.operational.read",
    "cash.user_cut.capture",
    "cash.user_cut.finalize",
    "financial.data.read",
    "financial.delegations.manage",
    "reports.operational.read",
    "purchases.prices.read",
    "purchases.receive",
    "inventory.costs.read",
)


def _user_fk(column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", column],
        ["users.organization_id", "users.id"],
    )


def tables(metadata: sa.MetaData) -> tuple[sa.Table, ...]:
    reviews = sa.Table(
        "financial_owner_reviews",
        metadata,
        sa.Column("organization_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("authorization_version", sa.Integer, primary_key=True),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("approval_reference", sa.String(500), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("user_id"),
        sa.CheckConstraint("authorization_version >= 1", name="ck_fin_owner_version"),
        sa.CheckConstraint("length(manifest_digest) = 64", name="ck_fin_owner_digest"),
        sa.CheckConstraint("trim(approval_reference) != ''", name="ck_fin_owner_reference"),
    )
    grants = sa.Table(
        "financial_access_grants",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("subject_user_id", sa.String(36), nullable=False),
        sa.Column("issuer_user_id", sa.String(36), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("authorization_version_at_issue", sa.Integer, nullable=False),
        _user_fk("subject_user_id"),
        _user_fk("issuer_user_id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_fin_grant_org_id"),
        sa.CheckConstraint("trim(reason) != ''", name="ck_fin_grant_reason"),
        sa.CheckConstraint("authorization_version_at_issue >= 1", name="ck_fin_grant_version"),
        sa.Index("ix_fin_grants_subject", "organization_id", "subject_user_id"),
    )
    scopes = sa.Table(
        "financial_access_grant_scopes",
        metadata,
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("grant_id", sa.String(36), primary_key=True),
        sa.Column("branch_id", sa.String(36), primary_key=True),
        sa.Column("dataset", sa.String(32), primary_key=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "grant_id"],
            ["financial_access_grants.organization_id", "financial_access_grants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["branches.organization_id", "branches.id"],
        ),
        sa.CheckConstraint(f"dataset IN {DATASETS!r}", name="ck_fin_scope_dataset"),
    )
    commands = sa.Table(
        "financial_access_commands",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("grant_id", sa.String(36), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("actor_user_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "grant_id"],
            ["financial_access_grants.organization_id", "financial_access_grants.id"],
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_fin_command_org_id"),
        sa.UniqueConstraint(
            "organization_id", "actor_user_id", "idempotency_key", name="uq_fin_command_actor_key"
        ),
        sa.CheckConstraint("trim(idempotency_key) != ''", name="ck_fin_command_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_fin_command_hash"),
        sa.CheckConstraint("action IN ('issue', 'revoke')", name="ck_fin_command_action"),
        sa.CheckConstraint(
            "outcome IN ('issued', 'revoked', 'already_revoked')", name="ck_fin_command_outcome"
        ),
    )
    revocations = sa.Table(
        "financial_access_grant_revocations",
        metadata,
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("grant_id", sa.String(36), primary_key=True),
        sa.Column("revoked_by", sa.String(36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("command_id", sa.String(36), nullable=False, unique=True),
        _user_fk("revoked_by"),
        sa.ForeignKeyConstraint(
            ["organization_id", "grant_id"],
            ["financial_access_grants.organization_id", "financial_access_grants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "command_id"],
            ["financial_access_commands.organization_id", "financial_access_commands.id"],
        ),
        sa.CheckConstraint("trim(reason) != ''", name="ck_fin_revoke_reason"),
    )
    policy = sa.Table(
        "blind_cash_policy_revisions",
        metadata,
        sa.Column("organization_id", sa.String(36), primary_key=True),
        sa.Column("branch_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer, primary_key=True),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("minimum_api_version", sa.Integer, nullable=False),
        sa.Column("minimum_client_version", sa.Integer, nullable=False),
        sa.Column("minimum_gateway_version", sa.Integer, nullable=False),
        sa.Column("event", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["branches.organization_id", "branches.id"],
        ),
        sa.CheckConstraint("revision >= 1", name="ck_blind_policy_revision"),
        sa.CheckConstraint("length(manifest_digest) = 64", name="ck_blind_policy_digest"),
        sa.CheckConstraint(
            "minimum_api_version >= 2 AND minimum_client_version >= 2 "
            "AND minimum_gateway_version >= 2",
            name="ck_blind_policy_versions",
        ),
        sa.CheckConstraint(
            "event IN ('prepared', 'activated', 'suspended')", name="ck_blind_policy_event"
        ),
    )
    return reviews, grants, scopes, commands, revocations, policy


def install_immutability(connection: sa.Connection, relations: tuple[sa.Table, ...]) -> None:
    """DDL identifiers come exclusively from the fixed schema above."""
    dialect = connection.dialect.name
    if dialect == "postgresql":
        connection.execute(
            sa.text("""
            CREATE FUNCTION reject_financial_authority_mutation() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'financial authority evidence is append-only'; END;
            $$ LANGUAGE plpgsql
        """)
        )
    for table in relations:
        if dialect == "postgresql":
            connection.execute(
                sa.text(
                    f"CREATE TRIGGER immutable_{table.name} "
                    f"BEFORE UPDATE OR DELETE ON {table.name} "
                    "FOR EACH ROW EXECUTE FUNCTION reject_financial_authority_mutation()"
                )
            )
        elif dialect == "sqlite":
            for action in ("UPDATE", "DELETE"):
                connection.execute(
                    sa.text(
                        f"CREATE TRIGGER immutable_{table.name}_{action.lower()} "
                        f"BEFORE {action} ON {table.name} BEGIN "
                        "SELECT RAISE(ABORT, 'financial authority evidence is append-only'); END"
                    )
                )
        else:
            raise RuntimeError("Financial authority requires PostgreSQL or SQLite")

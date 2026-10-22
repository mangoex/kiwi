"""Exact supervisor authorizations; no credentials or financial snapshots."""

import sqlalchemy as sa

CAPABILITY = "orders.exceptions.authorize"


def tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table]:
    authorizations = sa.Table(
        "order_exception_authorizations",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("supervisor_user_id", sa.String(36), nullable=False),
        sa.Column("supervisor_version", sa.Integer, nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("expected_version", sa.Integer, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"], ["branches.organization_id", "branches.id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"], ["users.organization_id", "users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "supervisor_user_id"], ["users.organization_id", "users.id"]
        ),
        sa.CheckConstraint("action IN ('amend','cancel')", name="ck_order_exception_action"),
        sa.CheckConstraint(
            "expected_version >= 1 AND supervisor_version >= 1", name="ck_order_exception_versions"
        ),
        sa.CheckConstraint(
            "length(request_hash) = 64 AND trim(reason) != ''", name="ck_order_exception_content"
        ),
    )
    consumptions = sa.Table(
        "order_exception_consumptions",
        metadata,
        sa.Column(
            "authorization_id", sa.String(36), sa.ForeignKey(authorizations.c.id), primary_key=True
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
    )
    return authorizations, consumptions

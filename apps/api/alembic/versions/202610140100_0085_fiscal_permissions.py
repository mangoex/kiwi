"""Register explicit fiscal capabilities without silently assigning ordinary roles."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import sqlalchemy as sa
from alembic import op

revision = "0085_fiscal_permissions"
down_revision = "0084_branch_workspaces"
branch_labels = depends_on = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
CODES = (
    "invoicing.read",
    "invoicing.issue",
    "invoicing.cancel",
    "invoicing.receipt.create",
    "invoicing.config.manage",
)
PERMISSIONS = {code: str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + code)) for code in CODES}


def _authority_fence(bind: sa.Connection) -> list[dict[str, object]]:
    if bind.dialect.name == "sqlite":
        driver = bind.connection.driver_connection
        if not getattr(driver, "in_transaction", True):
            bind.execute(sa.text("BEGIN IMMEDIATE"))
    else:
        # Same namespace/order as operations._authority_governance_lock; then user row locks.
        for org in bind.execute(sa.text("SELECT id FROM organizations ORDER BY id")).scalars():
            bind.execute(
                sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"authority-governance:{ORGANIZATION_ID}:{org}"},
            )
    query = (
        "SELECT u.id, u.organization_id, u.authorization_version FROM users u WHERE EXISTS ("
        "SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id "
        "JOIN role_authority_grants g ON g.role_id=r.id "
        "WHERE ur.user_id=u.id AND r.organization_id=u.organization_id "
        "AND r.scope='organization' AND g.authority_kind='organization_all_permissions') "
        "ORDER BY u.organization_id, u.id"
    )
    if bind.dialect.name == "postgresql":
        query += " FOR UPDATE OF u"
    rows = [dict(row) for row in bind.execute(sa.text(query)).mappings()]
    if any(int(row["authorization_version"]) >= 2147483647 for row in rows):
        raise RuntimeError("0085 preflight failed: authorization version exhausted")
    return rows


def _bump_and_audit(bind: sa.Connection, owners: list[dict[str, object]], action: str) -> None:
    for row in owners:
        bind.execute(
            sa.text(
                "UPDATE users SET authorization_version=authorization_version+1 "
                "WHERE id=:id AND organization_id=:org"
            ),
            {"id": row["id"], "org": row["organization_id"]},
        )
    now = datetime.now(timezone.utc)
    for org in bind.execute(sa.text("SELECT id FROM organizations ORDER BY id")).scalars():
        bind.execute(
            sa.text(
                "INSERT INTO audit_events (id, organization_id, branch_id, actor_user_id, action, "
                "entity_type, entity_id, payload, correlation_id, created_at) "
                "VALUES (:id, :org, NULL, NULL, :action, 'permission_registry', :revision, :payload, NULL, :now)"
            ).bindparams(sa.bindparam("payload", type_=sa.JSON())),
            {
                "id": str(uuid4()),
                "org": org,
                "action": action,
                "revision": revision,
                "payload": {
                    "revision": revision,
                    "codes": list(CODES),
                    "affected_accounts": sum(row["organization_id"] == org for row in owners),
                },
                "now": now,
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    owners = _authority_fence(bind)
    for code, identifier in PERMISSIONS.items():
        if bind.execute(
            sa.text("SELECT 1 FROM permissions WHERE id=:id OR code=:code"),
            {"id": identifier, "code": code},
        ).first():
            raise RuntimeError("0085 preflight failed: fiscal permission identity exists")
    now = datetime.now(timezone.utc)
    for code, identifier in PERMISSIONS.items():
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, created_at) "
                "VALUES (:id, :code, :description, :now)"
            ),
            {"id": identifier, "code": code, "description": code, "now": now},
        )
    _bump_and_audit(bind, owners, "rbac.fiscal_permissions_added")


def downgrade() -> None:
    bind = op.get_bind()
    owners = _authority_fence(bind)
    assignments = bind.execute(
        sa.text("SELECT 1 FROM role_permissions WHERE permission_id IN :ids LIMIT 1").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": list(PERMISSIONS.values())},
    ).first()
    if assignments or any(
        bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
        for table in ("facturapi_config", "cfdi_invoices")
    ):
        raise RuntimeError("0085 downgrade blocked: fiscal authority or history exists")
    for code, identifier in PERMISSIONS.items():
        current = bind.execute(
            sa.text("SELECT code FROM permissions WHERE id=:id"), {"id": identifier}
        ).scalar_one_or_none()
        if current != code:
            raise RuntimeError("0085 downgrade blocked: fiscal permission identity differs")
    for code, identifier in PERMISSIONS.items():
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id=:id AND code=:code"),
            {"id": identifier, "code": code},
        )
    _bump_and_audit(bind, owners, "rbac.fiscal_permissions_removed")

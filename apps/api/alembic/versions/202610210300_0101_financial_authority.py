"""F1-04 authority only: no role assignment, Owner inference or policy activation."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from restaurant_os.financial_access_schema import CAPABILITIES, install_immutability, tables

revision = "0101_financial_authority"
down_revision = "0100_delivery_fee"
branch_labels = depends_on = None


def _tables():
    metadata = sa.MetaData()
    for name in ("users", "branches"):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True),
                 sa.Column("organization_id", sa.String(36)))
    return tables(metadata)


def upgrade() -> None:
    connection = op.get_bind()
    relations = _tables()
    for relation in relations:
        relation.create(connection)
    install_immutability(connection, relations)
    for code in CAPABILITIES:
        if not connection.scalar(sa.text("SELECT id FROM permissions WHERE code = :code"),
                                 {"code": code}):
            connection.execute(sa.text(
                "INSERT INTO permissions (id, code, description, created_at) "
                "VALUES (:id, :code, :description, :created_at)"
            ), {"id": str(uuid5(NAMESPACE_URL, "restaurantos/financial-capability/" + code)),
                "code": code, "description": "CORTE-CIEGO-001: " + code,
                "created_at": datetime.now(timezone.utc)})


def downgrade() -> None:
    connection = op.get_bind()
    relations = _tables()
    if any(connection.scalar(sa.select(sa.func.count()).select_from(t)) for t in relations):
        raise RuntimeError("0101 downgrade blocked: financial authority evidence exists")
    for code in CAPABILITIES:
        assigned = connection.scalar(sa.text(
            "SELECT COUNT(*) FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id "
            "WHERE p.code=:code"
        ), {"code": code})
        if assigned:
            raise RuntimeError("0101 downgrade blocked: financial capabilities are assigned")
    for relation in reversed(relations):
        relation.drop(connection)
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("DROP FUNCTION reject_financial_authority_mutation()"))
    for code in CAPABILITIES:
        connection.execute(sa.text("DELETE FROM permissions WHERE id=:id AND code=:code"), {
            "id": str(uuid5(NAMESPACE_URL, "restaurantos/financial-capability/" + code)),
            "code": code,
        })

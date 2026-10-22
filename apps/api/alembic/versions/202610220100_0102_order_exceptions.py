"""Exact order exceptions, without inferred role assignment or rollout."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from restaurant_os.financial_access_schema import install_immutability
from restaurant_os.order_exception_schema import CAPABILITY, tables

revision = "0102_order_exceptions"
down_revision = "0101_financial_authority"
branch_labels = depends_on = None


def relations():
    metadata = sa.MetaData()
    for name in ("users", "branches", "orders"):
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36)),
        )
    return tables(metadata)


def upgrade() -> None:
    bind = op.get_bind()
    for relation in relations():
        relation.create(bind)
    if bind.dialect.name == "postgresql":
        # 0101 owns this function; only install triggers for the new evidence.
        for relation in relations():
            bind.execute(
                sa.text(
                    f"CREATE TRIGGER immutable_{relation.name} "
                    f"BEFORE UPDATE OR DELETE ON {relation.name} FOR EACH ROW "
                    "EXECUTE FUNCTION reject_financial_authority_mutation()"
                )
            )
    else:
        install_immutability(bind, relations())
    if not bind.scalar(
        sa.text("SELECT id FROM permissions WHERE code=:code"), {"code": CAPABILITY}
    ):
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id,code,description,created_at) VALUES (:id,:code,:description,:at)"
            ),
            {
                "id": str(uuid5(NAMESPACE_URL, "restaurantos/financial-capability/" + CAPABILITY)),
                "code": CAPABILITY,
                "description": "Autorizar excepciones exactas de pedidos",
                "at": datetime.now(timezone.utc),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    if any(bind.scalar(sa.select(sa.func.count()).select_from(table)) for table in relations()):
        raise RuntimeError("0102 downgrade blocked: order authorization evidence exists")
    if bind.scalar(
        sa.text(
            "SELECT count(*) FROM role_permissions r JOIN permissions p ON r.permission_id=p.id WHERE p.code=:code"
        ),
        {"code": CAPABILITY},
    ):
        raise RuntimeError("0102 downgrade blocked: capability assigned")
    for relation in reversed(relations()):
        relation.drop(bind)
    bind.execute(
        sa.text("DELETE FROM permissions WHERE id=:id AND code=:code"),
        {
            "id": str(uuid5(NAMESPACE_URL, "restaurantos/financial-capability/" + CAPABILITY)),
            "code": CAPABILITY,
        },
    )

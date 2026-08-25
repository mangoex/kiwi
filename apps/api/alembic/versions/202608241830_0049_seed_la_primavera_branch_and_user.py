from __future__ import annotations

# ruff: noqa: E501
"""seed and link la primavera branch and cashier user

Revision ID: 0049_seed_la_primavera_branch_and_user
Revises: 0048_sync_insumos_and_presentations
Create Date: 2026-08-24 18:30:00.000000

"""
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0049_seed_la_primavera_branch_and_user"
down_revision: str | None = "0048_sync_insumos_and_presentations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
LA_PRIMAVERA_BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
LA_PRIMAVERA_WAREHOUSE_ID = "018f6f73-2d0a-74f0-8f1c-000000000102"


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # 1. Look up or obtain legal entity and business unit
    legal_entity_id = conn.execute(
        sa.text("SELECT id FROM legal_entities WHERE organization_id = :org_id LIMIT 1"),
        {"org_id": ORGANIZATION_ID},
    ).scalar_one_or_none()

    if not legal_entity_id:
        legal_entity_id = str(uuid.uuid4())
        conn.execute(
            sa.text("""
                INSERT INTO legal_entities (id, organization_id, name, rfc, regimen_fiscal, postal_code, is_active, created_at, updated_at)
                VALUES (:id, :org_id, 'RESTAURANTE OPERADORA SA DE CV', 'ROP200101ABC', '601', '80000', true, :now, :now)
            """),
            {"id": legal_entity_id, "org_id": ORGANIZATION_ID, "now": now},
        )

    business_unit_id = conn.execute(
        sa.text("SELECT id FROM business_units WHERE organization_id = :org_id LIMIT 1"),
        {"org_id": ORGANIZATION_ID},
    ).scalar_one_or_none()

    if not business_unit_id:
        business_unit_id = str(uuid.uuid4())
        conn.execute(
            sa.text("""
                INSERT INTO business_units (id, organization_id, code, name, unit_type, status, created_at, updated_at)
                VALUES (:id, :org_id, 'REST', 'Restaurantes', 'restaurant', 'active', :now, :now)
            """),
            {"id": business_unit_id, "org_id": ORGANIZATION_ID, "now": now},
        )

    # 2. Look up or create Branch 'La Primavera'
    primavera_branch = conn.execute(
        sa.text("""
            SELECT id FROM branches 
            WHERE organization_id = :org_id 
              AND (UPPER(name) LIKE '%PRIMAVERA%' OR UPPER(code) LIKE '%PRIMAVERA%' OR UPPER(code) = 'SUC02')
            LIMIT 1
        """),
        {"org_id": ORGANIZATION_ID},
    ).scalar_one_or_none()

    if not primavera_branch:
        primavera_branch_id = LA_PRIMAVERA_BRANCH_ID
        conn.execute(
            sa.text("""
                INSERT INTO branches (
                    id, organization_id, legal_entity_id, business_unit_id,
                    name, code, timezone, status, city, state, created_at, updated_at
                ) VALUES (
                    :id, :org_id, :legal_id, :bu_id,
                    'La Primavera', 'SUC02', 'America/Chihuahua', 'active', 'Culiacán', 'Sinaloa', :now, :now
                )
            """),
            {
                "id": primavera_branch_id,
                "org_id": ORGANIZATION_ID,
                "legal_id": legal_entity_id,
                "bu_id": business_unit_id,
                "now": now,
            },
        )
    else:
        primavera_branch_id = str(primavera_branch)

    # 3. Look up or create Warehouse for La Primavera
    warehouse_exists = conn.execute(
        sa.text("SELECT id FROM warehouses WHERE branch_id = :branch_id LIMIT 1"),
        {"branch_id": primavera_branch_id},
    ).scalar_one_or_none()

    if not warehouse_exists:
        conn.execute(
            sa.text("""
                INSERT INTO warehouses (id, organization_id, branch_id, name, status, created_at, updated_at)
                VALUES (:id, :org_id, :branch_id, 'Almacén La Primavera', 'active', :now, :now)
            """),
            {
                "id": LA_PRIMAVERA_WAREHOUSE_ID,
                "org_id": ORGANIZATION_ID,
                "branch_id": primavera_branch_id,
                "now": now,
            },
        )

    # 4. Look up or create User 'caja01laprimavera@kiwi.com'
    cashier_user_id = conn.execute(
        sa.text("SELECT id FROM users WHERE organization_id = :org_id AND LOWER(email) = 'caja01laprimavera@kiwi.com' LIMIT 1"),
        {"org_id": ORGANIZATION_ID},
    ).scalar_one_or_none()

    if not cashier_user_id:
        cashier_user_id = str(uuid.uuid4())
        conn.execute(
            sa.text("""
                INSERT INTO users (id, organization_id, email, display_name, status, created_at, updated_at)
                VALUES (:id, :org_id, 'caja01laprimavera@kiwi.com', 'Caja 01 La Primavera', 'active', :now, :now)
            """),
            {"id": cashier_user_id, "org_id": ORGANIZATION_ID, "now": now},
        )
    else:
        cashier_user_id = str(cashier_user_id)

    # 5. Look up Role 'Cajero' / 'Cajero Jefe' / 'Líder'
    cajero_role_id = conn.execute(
        sa.text("SELECT id FROM roles WHERE organization_id = :org_id AND (name = 'Cajero' OR name = 'Cajero Jefe') ORDER BY name DESC LIMIT 1"),
        {"org_id": ORGANIZATION_ID},
    ).scalar_one_or_none()

    if not cajero_role_id:
        # Fallback to any role in organization
        cajero_role_id = conn.execute(
            sa.text("SELECT id FROM roles WHERE organization_id = :org_id LIMIT 1"),
            {"org_id": ORGANIZATION_ID},
        ).scalar_one()

    # 6. Re-link cashier user role assignment to La Primavera branch specifically
    conn.execute(
        sa.text("DELETE FROM user_roles WHERE user_id = :user_id"),
        {"user_id": cashier_user_id},
    )

    conn.execute(
        sa.text("""
            INSERT INTO user_roles (user_id, role_id, branch_id)
            VALUES (:user_id, :role_id, :branch_id)
        """),
        {
            "user_id": cashier_user_id,
            "role_id": str(cajero_role_id),
            "branch_id": primavera_branch_id,
        },
    )


def downgrade() -> None:
    pass
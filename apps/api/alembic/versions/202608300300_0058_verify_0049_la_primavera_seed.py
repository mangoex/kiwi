"""Contain legacy 0049 through an exact clean or owner-approved canonical state.

Revision ID: 0058_verify_0049_la_primavera_seed
Revises: 0057_operational_human_scope_permissions
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0058_verify_0049_la_primavera_seed"
down_revision: str | None = "0057_operational_human_scope_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
CAJERO_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000001001"
AUDIT_ID = "018f6f73-2d0a-74f0-8f1c-000000001200"
ACCOUNT_EMAIL = "caja01laprimavera@kiwi.com"


def _one_mapping(rows: list[sa.RowMapping], missing: str, ambiguous: str) -> sa.RowMapping:
    if not rows:
        raise RuntimeError(missing)
    if len(rows) != 1:
        raise RuntimeError(ambiguous)
    return rows[0]


def _same_seed_timestamp(*rows: sa.RowMapping) -> bool:
    timestamps: list[Any] = []
    for row in rows:
        created_at = row["created_at"]
        updated_at = row["updated_at"]
        if created_at != updated_at:
            return False
        timestamps.append(created_at)
    return len(set(timestamps)) == 1


def _preflight(bind: sa.Connection) -> tuple[str, str, str]:
    organization = bind.execute(
        sa.text("SELECT id FROM organizations WHERE id = :organization_id"),
        {"organization_id": ORGANIZATION_ID},
    ).first()
    if organization is None:
        raise RuntimeError("0058 preflight failed: canonical organization is missing")

    branch = _one_mapping(
        list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, organization_id, name, code, timezone, status, city, state,
                           created_at, updated_at
                    FROM branches
                    WHERE organization_id = :organization_id
                      AND LOWER(TRIM(name)) = 'la primavera'
                    """
                ),
                {"organization_id": ORGANIZATION_ID},
            ).mappings()
        ),
        "0058 preflight failed: exact La Primavera branch is missing; manual data review required",
        "0058 preflight failed: multiple exact La Primavera branches require manual data review",
    )
    branch_id = str(branch["id"])

    warehouse = _one_mapping(
        list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, organization_id, branch_id, name, status, created_at, updated_at
                    FROM warehouses WHERE branch_id = :branch_id
                    """
                ),
                {"branch_id": branch_id},
            ).mappings()
        ),
        "0058 preflight failed: La Primavera warehouse is missing",
        "0058 preflight failed: multiple La Primavera warehouses require manual data review",
    )

    user = _one_mapping(
        list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, organization_id, email, display_name, status,
                           created_at, updated_at
                    FROM users WHERE LOWER(email) = :email
                    """
                ),
                {"email": ACCOUNT_EMAIL},
            ).mappings()
        ),
        "0058 preflight failed: La Primavera cashier account is missing",
        "0058 preflight failed: duplicate La Primavera cashier accounts require manual review",
    )
    user_id = str(user["id"])

    role = bind.execute(
        sa.text(
            """
            SELECT id, organization_id, name, scope FROM roles WHERE id = :role_id
            """
        ),
        {"role_id": CAJERO_ROLE_ID},
    ).mappings().one_or_none()
    if role is None or (
        str(role["organization_id"]) != ORGANIZATION_ID
        or role["name"] != "Cajero"
        or role["scope"] != "branch"
    ):
        raise RuntimeError("0058 preflight failed: canonical Cajero role identity differs")

    approved_suc06_state_matches = branch["code"] == "SUC06"
    warehouse_name_matches = warehouse["name"] == "Almacén La Primavera" or (
        approved_suc06_state_matches and warehouse["name"] == "Almacen La Primavera"
    )
    canonical_identity_matches = (
        str(branch["organization_id"]) == ORGANIZATION_ID
        and branch["name"] == "La Primavera"
        and branch["timezone"] == "America/Chihuahua"
        and branch["status"] == "active"
        and branch["city"] == "Culiacán"
        and branch["state"] == "Sinaloa"
        and str(warehouse["organization_id"]) == ORGANIZATION_ID
        and str(warehouse["branch_id"]) == branch_id
        and warehouse_name_matches
        and warehouse["status"] == "active"
        and str(user["organization_id"]) == ORGANIZATION_ID
        and str(user["email"]).lower() == ACCOUNT_EMAIL
        and user["display_name"] == "Caja 01 La Primavera"
        and user["status"] == "active"
    )
    clean_seed_fingerprint_matches = (
        branch["code"] in {"SUC02", "PRIMAVERA"}
        and _same_seed_timestamp(branch, warehouse, user)
    )
    if not canonical_identity_matches or not (
        clean_seed_fingerprint_matches or approved_suc06_state_matches
    ):
        raise RuntimeError(
            "0058 preflight failed: pre-existing account requires manual role reconciliation"
        )
    decision = (
        "clean_seed_fingerprint_verified"
        if clean_seed_fingerprint_matches
        else "approved_canonical_state_verified"
    )

    assignments = list(
        bind.execute(
            sa.text(
                """
                SELECT role_id, branch_id FROM user_roles
                WHERE user_id = :user_id
                ORDER BY role_id, branch_id
                """
            ),
            {"user_id": user_id},
        ).mappings()
    )
    if len(assignments) != 1 or (
        str(assignments[0]["role_id"]) != CAJERO_ROLE_ID
        or str(assignments[0]["branch_id"]) != branch_id
    ):
        raise RuntimeError(
            "0058 preflight failed: current assignments require manual role reconciliation"
        )

    if bind.execute(
        sa.text("SELECT id FROM audit_events WHERE id = :audit_id"), {"audit_id": AUDIT_ID}
    ).first():
        raise RuntimeError("0058 preflight failed: reserved audit identity already exists")
    return user_id, branch_id, decision


def upgrade() -> None:
    bind = op.get_bind()
    user_id, branch_id, decision = _preflight(bind)
    bind.execute(
        sa.text(
            """
            INSERT INTO audit_events (
                id, organization_id, branch_id, actor_user_id, action, entity_type,
                entity_id, payload, correlation_id, created_at
            ) VALUES (
                :id, :organization_id, :branch_id, NULL, :action, :entity_type,
                :entity_id, :payload, NULL, :created_at
            )
            """
        ).bindparams(sa.bindparam("payload", type_=sa.JSON())),
        {
            "id": AUDIT_ID,
            "organization_id": ORGANIZATION_ID,
            "branch_id": branch_id,
            "action": "migration.0049_seed_state_verified",
            "entity_type": "user_role_seed",
            "entity_id": user_id,
            "payload": {
                "assignment_snapshot": [
                    {"branch_id": branch_id, "role_id": CAJERO_ROLE_ID}
                ],
                "decision": decision,
                "source_revision": "0049_seed_la_primavera_branch_and_user",
                "verification_revision": revision,
            },
            "created_at": datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc),
        },
    )


def downgrade() -> None:
    raise RuntimeError(
        "0058 is forward-only: deleting verification audit or reconstructing roles lost by 0049 "
        "would be unsafe"
    )

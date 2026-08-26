"""Seed standard cash movement concepts (compras en efectivo, comisiones, propinas, salvaguardas, etc.)

Revision ID: 0054_seed_standard_cash_movement_concepts
Revises: 0053_cash_offline_sync
Create Date: 2026-08-26 12:00:00
"""

from __future__ import annotations

import datetime
import uuid
from alembic import op
import sqlalchemy as sa

revision: str = "0054_seed_standard_cash_movement_concepts"
down_revision: str | None = "0053_cash_offline_sync"
branch_labels = None
depends_on = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
SUPERADMIN_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"

STANDARD_CONCEPTS = [
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000001",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000001",
        "code": "001",
        "name": "COMPRAS EN EFECTIVO",
        "allowed_movement_type": "withdrawal",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000002",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000002",
        "code": "002",
        "name": "COMISIONES",
        "allowed_movement_type": "withdrawal",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000003",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000003",
        "code": "003",
        "name": "PROPINAS",
        "allowed_movement_type": "both",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000004",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000004",
        "code": "004",
        "name": "SALVAGUARDAS",
        "allowed_movement_type": "withdrawal",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000005",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000005",
        "code": "005",
        "name": "APORTE DE EFECTIVO",
        "allowed_movement_type": "deposit",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000006",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000006",
        "code": "006",
        "name": "FONDO DE CAJA",
        "allowed_movement_type": "deposit",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000007",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000007",
        "code": "007",
        "name": "RETIRO GENERAL",
        "allowed_movement_type": "withdrawal",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-conc00000008",
        "version_id": "018f6f73-2d0a-74f0-8f1c-cver00000008",
        "code": "008",
        "name": "INGRESO GENERAL",
        "allowed_movement_type": "deposit",
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    valid_from = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)

    concepts_table = sa.Table(
        "cash_movement_concepts",
        sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )

    versions_table = sa.Table(
        "cash_movement_concept_versions",
        sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("concept_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("allowed_movement_type", sa.String(16), nullable=False),
        sa.Column("requires_reference", sa.Boolean(), nullable=False),
        sa.Column("requires_evidence", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    for item in STANDARD_CONCEPTS:
        # Check if code already exists
        existing = bind.execute(
            sa.select(concepts_table.c.id).where(
                concepts_table.c.organization_id == ORGANIZATION_ID,
                concepts_table.c.code == item["code"],
            )
        ).scalar()

        if not existing:
            bind.execute(
                concepts_table.insert().values(
                    id=item["id"],
                    organization_id=ORGANIZATION_ID,
                    code=item["code"],
                    status="active",
                    created_by_user_id=SUPERADMIN_ID,
                    created_at=now,
                    archived_at=None,
                )
            )
            bind.execute(
                versions_table.insert().values(
                    id=item["version_id"],
                    concept_id=item["id"],
                    version=1,
                    name=item["name"],
                    allowed_movement_type=item["allowed_movement_type"],
                    requires_reference=True,
                    requires_evidence=True,
                    valid_from=valid_from,
                    created_by_user_id=SUPERADMIN_ID,
                    created_at=now,
                )
            )


def downgrade() -> None:
    pass

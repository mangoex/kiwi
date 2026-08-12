"""extend the compatible cash ledger with PCO-003 commands

Revision ID: 0037_cash_movement_ledger
Revises: 0036_cash_concepts
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_cash_movement_ledger"
down_revision: str | None = "0036_cash_concepts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text("""
        SELECT 1 FROM cash_shifts
        WHERE upper(status) = 'OPEN'
        GROUP BY branch_id, register_code HAVING count(*) > 1 LIMIT 1
    """)
    ).scalar_one_or_none()
    if duplicate:
        raise RuntimeError("Cash shift preflight failed: duplicate OPEN shifts")
    incoherent_reversal = bind.execute(sa.text("""
        SELECT 1 FROM cash_movements movement
        LEFT JOIN cash_movements original ON original.id = movement.reversal_of_id
        WHERE movement.reversal_of_id IS NOT NULL AND original.id IS NULL LIMIT 1
    """)).scalar_one_or_none()
    if incoherent_reversal:
        raise RuntimeError("Cash movement preflight failed: incoherent legacy reversal")
    with op.batch_alter_table("cash_movements") as batch:
        batch.add_column(sa.Column("concept_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("concept_version_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("concept_snapshot", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("reference", sa.String(600), nullable=True))
        batch.add_column(sa.Column("evidence_refs", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("compensates_movement_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_cash_movements_concept", "cash_movement_concepts", ["concept_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_cash_movements_concept_version",
            "cash_movement_concept_versions",
            ["concept_version_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_cash_movements_compensates", "cash_movements", ["compensates_movement_id"], ["id"]
        )
    op.create_index(
        "uq_cash_movements_compensates_movement",
        "cash_movements",
        ["compensates_movement_id"],
        unique=True,
        sqlite_where=sa.text("compensates_movement_id IS NOT NULL"),
        postgresql_where=sa.text("compensates_movement_id IS NOT NULL"),
    )
    op.create_index(
        "uq_cash_shifts_open_register",
        "cash_shifts",
        ["branch_id", "register_code"],
        unique=True,
        sqlite_where=sa.text("upper(status) = 'OPEN'"),
        postgresql_where=sa.text("upper(status) = 'OPEN'"),
    )
    op.create_index(
        "ix_cash_movements_branch_shift_created",
        "cash_movements",
        ["branch_id", "cash_shift_id", "created_at"],
    )
    op.create_table(
        "cash_movement_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "target_movement_id", sa.String(36), sa.ForeignKey("cash_movements.id"), nullable=True
        ),
        sa.Column("command_type", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "command_type IN ('create', 'compensate')", name="ck_cash_movement_commands_type"
        ),
        sa.CheckConstraint("status = 'completed'", name="ck_cash_movement_commands_status"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_cash_movement_commands_org_key"
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    command_count = int(
        bind.execute(sa.text("SELECT COUNT(*) FROM cash_movement_commands")).scalar_one()
    )
    movement_count = int(
        bind.execute(
            sa.text("""
        SELECT COUNT(*) FROM cash_movements
        WHERE concept_id IS NOT NULL OR concept_version_id IS NOT NULL OR concept_snapshot IS NOT NULL
           OR reference IS NOT NULL OR evidence_refs IS NOT NULL OR compensates_movement_id IS NOT NULL
    """)
        ).scalar_one()
    )
    if command_count or movement_count:
        raise RuntimeError("Safe downgrade blocked: cash movement ledger history exists")
    op.drop_table("cash_movement_commands")
    op.drop_index("uq_cash_shifts_open_register", table_name="cash_shifts")
    op.drop_index("ix_cash_movements_branch_shift_created", table_name="cash_movements")
    op.drop_index("uq_cash_movements_compensates_movement", table_name="cash_movements")
    with op.batch_alter_table("cash_movements") as batch:
        batch.drop_constraint("fk_cash_movements_compensates", type_="foreignkey")
        batch.drop_constraint("fk_cash_movements_concept_version", type_="foreignkey")
        batch.drop_constraint("fk_cash_movements_concept", type_="foreignkey")
        batch.drop_column("compensates_movement_id")
        batch.drop_column("evidence_refs")
        batch.drop_column("reference")
        batch.drop_column("concept_snapshot")
        batch.drop_column("concept_version_id")
        batch.drop_column("concept_id")

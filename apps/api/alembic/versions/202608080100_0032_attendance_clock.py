"""attendance clock and employee codes

Revision ID: 0032_attendance_clock
Revises: 0031_delivery_assignments
Create Date: 2026-08-08 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_attendance_clock"
down_revision: str | None = "0031_delivery_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_code_registry",
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            primary_key=True,
        ),
        sa.Column("employee_code", sa.String(6), primary_key=True),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(employee_code) = 6",
            name="ck_employee_code_registry_length",
        ),
        sa.CheckConstraint(
            "subject_type IN ('user', 'driver')",
            name="ck_employee_code_registry_subject_type",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "subject_type",
            "subject_id",
            name="uq_employee_code_registry_subject",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "employee_code",
            "subject_id",
            name="uq_employee_code_registry_reference",
        ),
    )
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("employee_code", sa.String(6), nullable=True))
        batch.create_unique_constraint(
            "uq_users_organization_employee_code",
            ["organization_id", "employee_code"],
        )
        batch.create_check_constraint(
            "ck_users_employee_code_length",
            "employee_code IS NULL OR length(employee_code) = 6",
        )
        batch.create_foreign_key(
            "fk_users_employee_code_registry",
            "employee_code_registry",
            ["organization_id", "employee_code", "id"],
            ["organization_id", "employee_code", "subject_id"],
            onupdate="CASCADE",
        )
    with op.batch_alter_table("drivers") as batch:
        batch.add_column(sa.Column("employee_code", sa.String(6), nullable=True))
        batch.create_unique_constraint(
            "uq_drivers_organization_employee_code",
            ["organization_id", "employee_code"],
        )
        batch.create_check_constraint(
            "ck_drivers_employee_code_length",
            "employee_code IS NULL OR length(employee_code) = 6",
        )
        batch.create_foreign_key(
            "fk_drivers_employee_code_registry",
            "employee_code_registry",
            ["organization_id", "employee_code", "id"],
            ["organization_id", "employee_code", "subject_id"],
            onupdate="CASCADE",
        )

    op.create_table(
        "attendance_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("branches.id"),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("employee_code_snapshot", sa.String(6), nullable=False),
        sa.Column("employee_name_snapshot", sa.String(160), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("daily_sequence", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "subject_type IN ('user', 'driver')",
            name="ck_attendance_checks_subject_type",
        ),
        sa.CheckConstraint(
            "daily_sequence IN (1, 2)",
            name="ck_attendance_checks_daily_sequence",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "subject_type",
            "subject_id",
            "local_date",
            "daily_sequence",
            name="uq_attendance_checks_daily_sequence",
        ),
    )
    op.create_index(
        "ix_attendance_checks_branch_date",
        "attendance_checks",
        ["organization_id", "branch_id", "local_date"],
    )
    op.create_index(
        "ix_attendance_checks_code_date",
        "attendance_checks",
        ["organization_id", "employee_code_snapshot", "local_date"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    attendance_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM attendance_checks")
    ).scalar_one()
    assigned_code_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM employee_code_registry")
    ).scalar_one()
    if attendance_count or assigned_code_count:
        raise RuntimeError(
            "Cannot downgrade 0032 while attendance checks or employee codes exist"
        )

    op.drop_index("ix_attendance_checks_code_date", table_name="attendance_checks")
    op.drop_index("ix_attendance_checks_branch_date", table_name="attendance_checks")
    op.drop_table("attendance_checks")
    with op.batch_alter_table("drivers") as batch:
        batch.drop_constraint("fk_drivers_employee_code_registry", type_="foreignkey")
        batch.drop_constraint("ck_drivers_employee_code_length", type_="check")
        batch.drop_constraint("uq_drivers_organization_employee_code", type_="unique")
        batch.drop_column("employee_code")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_employee_code_registry", type_="foreignkey")
        batch.drop_constraint("ck_users_employee_code_length", type_="check")
        batch.drop_constraint("uq_users_organization_employee_code", type_="unique")
        batch.drop_column("employee_code")
    op.drop_table("employee_code_registry")

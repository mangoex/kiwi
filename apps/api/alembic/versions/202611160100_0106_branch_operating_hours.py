"""Add branch_operating_hours table and seed default branch schedules."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0106_branch_operating_hours"
down_revision = "0105_mcp_oauth_bindings"
branch_labels = depends_on = None

DEFAULT_SCHEDULE = (
    (0, True, "07:00", "18:00"),
    (1, True, "07:00", "18:00"),
    (2, True, "07:00", "18:00"),
    (3, True, "07:00", "18:00"),
    (4, True, "07:00", "18:00"),
    (5, True, "07:30", "16:00"),
    (6, False, None, None),
)


def upgrade() -> None:
    op.create_table(
        "branch_operating_hours",
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("day_of_week", sa.SmallInteger(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("open_time", sa.String(5), nullable=True),
        sa.Column("close_time", sa.String(5), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_branch_operating_hours_day",
        ),
        sa.CheckConstraint(
            "(is_open = false AND open_time IS NULL AND close_time IS NULL) OR "
            "(is_open = true AND open_time IS NOT NULL AND close_time IS NOT NULL "
            "AND open_time < close_time)",
            name="ck_branch_operating_hours_times",
        ),
    )

    bind = op.get_bind()
    branches = sa.table(
        "branches",
        sa.column("id", sa.String(36)),
        sa.column("organization_id", sa.String(36)),
    )
    hours_table = sa.table(
        "branch_operating_hours",
        sa.column("branch_id", sa.String(36)),
        sa.column("day_of_week", sa.SmallInteger()),
        sa.column("organization_id", sa.String(36)),
        sa.column("is_open", sa.Boolean()),
        sa.column("open_time", sa.String(5)),
        sa.column("close_time", sa.String(5)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    branch_rows = bind.execute(sa.select(branches.c.id, branches.c.organization_id)).all()
    if branch_rows:
        seed_rows = [
            {
                "branch_id": branch_id,
                "day_of_week": day_of_week,
                "organization_id": org_id,
                "is_open": is_open,
                "open_time": open_time,
                "close_time": close_time,
                "updated_at": now,
            }
            for branch_id, org_id in branch_rows
            for day_of_week, is_open, open_time, close_time in DEFAULT_SCHEDULE
        ]
        bind.execute(hours_table.insert(), seed_rows)


def downgrade() -> None:
    op.drop_table("branch_operating_hours")

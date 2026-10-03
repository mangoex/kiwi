"""UIX-USABILITY-001 branch-scoped POS catalog appearance."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0073_pos_catalog_appearance"
down_revision = "0072_purchase_create_commands"
branch_labels = depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "pos_catalog_visuals_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Exclude concurrent preference writers before checking whether rollback
        # would discard an explicit branch configuration.
        bind.execute(sa.text("LOCK TABLE branches IN ACCESS EXCLUSIVE MODE"))
    configured = bind.execute(
        sa.text(
            "SELECT 1 FROM branches "
            "WHERE pos_catalog_visuals_enabled = false LIMIT 1"
        )
    ).first()
    if configured:
        raise RuntimeError(
            "Cannot downgrade 0073 while hidden catalog visuals are configured"
        )
    op.drop_column("branches", "pos_catalog_visuals_enabled")

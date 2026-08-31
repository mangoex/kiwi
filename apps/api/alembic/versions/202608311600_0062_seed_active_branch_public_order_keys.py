"""Seed active branch public order keys for public ordering.

Revision ID: 0062_seed_active_branch_public_order_keys
Revises: 0061_facturapi_invoicing_support
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import sqlalchemy as sa
from alembic import op

revision: str = "0062_seed_active_branch_public_order_keys"
down_revision: str | None = "0061_facturapi_invoicing_support"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    branches = bind.execute(
        sa.text("SELECT id, organization_id, code FROM branches WHERE status = 'active'")
    ).fetchall()

    for branch in branches:
        branch_id = str(branch[0])
        org_id = str(branch[1])
        # Check if already exists
        existing = bind.execute(
            sa.text("SELECT public_key FROM public_order_keys WHERE branch_id = :bid AND status = 'active'"),
            {"bid": branch_id},
        ).fetchone()
        if not existing:
            pk = f"pk_{branch_id.replace('-', '')[:24]}"
            now = datetime.now(timezone.utc)
            bind.execute(
                sa.text(
                    "INSERT INTO public_order_keys (public_key, organization_id, branch_id, status, created_at) "
                    "VALUES (:pk, :org, :bid, 'active', :now)"
                ),
                {"pk": pk, "org": org_id, "bid": branch_id, "now": now},
            )


def downgrade() -> None:
    pass

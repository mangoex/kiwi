from __future__ import annotations

"""bootstrap platform

Revision ID: 202607071730
Revises:
Create Date: 2026-07-07 17:30:00
"""

from collections.abc import Sequence

revision: str = "202607071730"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

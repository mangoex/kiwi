from __future__ import annotations

# ruff: noqa: E501
"""seed 315 product recipes from SoftRestaurant catalog

Revision ID: 0054_seed_recipes_from_pdf
Revises: 0053_cash_offline_sync
Create Date: 2026-08-25 18:00:00.000000

"""
from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy.orm import Session

from restaurant_os.recipe_pdf_loader import load_recipes_from_pdf

# revision identifiers, used by Alembic.
revision: str = "0054_seed_recipes_from_pdf"
down_revision: str | None = "0053_cash_offline_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    # Locate pdf and excel directory if available
    possible_roots = [
        Path(__file__).resolve().parents[4],  # Kiwi monorepo root
        Path(__file__).resolve().parents[3],  # apps root
        Path(__file__).resolve().parents[2],  # apps/api root
        Path.cwd(),
        Path("/app"),
        Path("/app/apps/api"),
    ]

    pdf_file = "productosestructura.frx.pdf"
    excel_dir = "."

    for r in possible_roots:
        cand_pdf = r / "productosestructura.frx.pdf"
        if cand_pdf.exists():
            pdf_file = str(cand_pdf)
            excel_dir = str(r)
            break
        cand_xls = r / "PRODUCTOS.XLS"
        if cand_xls.exists():
            excel_dir = str(r)

    load_recipes_from_pdf(
        session=session,
        pdf_path=pdf_file,
        excel_dir=excel_dir,
        organization_id=ORGANIZATION_ID,
    )


def downgrade() -> None:
    pass

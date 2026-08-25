from __future__ import annotations

# ruff: noqa: E501
"""seed 315 product recipes from productosestructura.frx.pdf

Revision ID: 0051_seed_recipes_from_pdf
Revises: 0050_promote_recipes_to_global_scope
Create Date: 2026-08-25 18:00:00.000000

"""
import os
from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy.orm import Session

from restaurant_os.recipe_pdf_loader import load_recipes_from_pdf

# revision identifiers, used by Alembic.
revision: str = "0051_seed_recipes_from_pdf"
down_revision: str | None = "0050_promote_recipes_to_global_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    # Locate pdf and excel directory
    # Possible locations: project root, api root, or current directory
    possible_roots = [
        Path(__file__).resolve().parents[4],  # Kiwi monorepo root
        Path(__file__).resolve().parents[3],  # apps root
        Path(__file__).resolve().parents[2],  # apps/api root
        Path.cwd(),
    ]

    pdf_file = None
    excel_dir = None

    for r in possible_roots:
        candidate_pdf = r / "productosestructura.frx.pdf"
        if candidate_pdf.exists():
            pdf_file = str(candidate_pdf)
            excel_dir = str(r)
            break

    if not excel_dir:
        excel_dir = str(possible_roots[0]) if possible_roots[0].exists() else "."
    if not pdf_file:
        pdf_file = "productosestructura.frx.pdf"

    load_recipes_from_pdf(
        session=session,
        pdf_path=pdf_file,
        excel_dir=excel_dir,
        organization_id=ORGANIZATION_ID,
    )


def downgrade() -> None:
    pass

"""Unit and Integration Tests for Recipe PDF Loader Module.

Verifies:
1. Parsing of productosestructura.frx.pdf.
2. Complete and idempotent loading of 315 recipes into the database.
3. Accurate reporting of configured recipes and skipped modifier sub-recipes.
4. Correct association between products, inventory items, units, and components.
"""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.recipe_pdf_loader import (
    load_recipes_from_pdf,
    parse_pdf_recipe_catalog,
)

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"


def test_parse_pdf_recipe_catalog() -> None:
    """Verifies that all recipes are parsed from productosestructura.frx.pdf."""
    root_dir = Path(__file__).resolve().parents[3]
    pdf_path = root_dir / "productosestructura.frx.pdf"
    assert pdf_path.exists(), f"PDF report not found at {pdf_path}"

    recipes = parse_pdf_recipe_catalog(str(pdf_path))
    assert len(recipes) == 329

    # Check sample recipe
    fresa_chica = next((r for r in recipes if r["sku"] == "01001"), None)
    assert fresa_chica is not None
    assert fresa_chica["name"] == "AGUA DE FRESA CHICA"
    assert fresa_chica["group"] == "AGUAS"
    assert len(fresa_chica["components"]) == 7


def test_load_recipes_from_pdf_and_verify_database_integrity(tmp_path: Path) -> None:
    """Migrates a fresh database and executes the full recipe sync workflow."""
    root_dir = Path(__file__).resolve().parents[3]
    pdf_path = str(root_dir / "productosestructura.frx.pdf")
    excel_dir = str(root_dir)

    database_path = tmp_path / "recipe_sync_test.db"
    db_url = f"sqlite+pysqlite:///{database_path}"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": db_url,
        "DATABASE_URL": db_url,
    }

    api_dir = str(Path(__file__).resolve().parents[1])

    # Run alembic upgrade head
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=api_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Alembic failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    engine = sa.create_engine(db_url)
    with Session(engine) as session:
        report = load_recipes_from_pdf(
            session=session,
            pdf_path=pdf_path,
            excel_dir=excel_dir,
            organization_id=ORGANIZATION_ID,
        )

        assert report["total_pdf_recipes"] == 329
        assert report["configured_count"] == 315
        assert report["skipped_count"] == 14

        # Verify database contents
        total_recipes_in_db = session.execute(
            sa.select(sa.func.count(models.recipes.c.id)).where(
                models.recipes.c.organization_id == ORGANIZATION_ID,
                models.recipes.c.status == "active",
            )
        ).scalar_one()
        assert total_recipes_in_db >= 315

        total_components_in_db = session.execute(
            sa.select(sa.func.count(models.recipe_components.c.recipe_id))
        ).scalar_one()
        assert total_components_in_db > 1000

        # Verify Coffee & Matcha recipes exist in DB
        cafe_solo = session.execute(
            sa.select(models.products.c.id, models.products.c.name).where(
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.sku.in_(["24001", "PROD-24001"]),
            )
        ).mappings().first()
        assert cafe_solo is not None
        assert cafe_solo["name"] == "CAFE SOLO"

        cafe_recipe = session.execute(
            sa.select(models.recipes.c.id).where(
                models.recipes.c.product_id == cafe_solo["id"],
                models.recipes.c.status == "active",
            )
        ).scalar_one_or_none()
        assert cafe_recipe is not None

        # Verify idempotency by running it again
        second_report = load_recipes_from_pdf(
            session=session,
            pdf_path=pdf_path,
            excel_dir=excel_dir,
            organization_id=ORGANIZATION_ID,
        )
        assert second_report["configured_count"] == 315
        assert second_report["skipped_count"] == 14

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.catalog_policy import (
    canonical_inventory_item_type,
    is_numeric_sku,
    is_uppercase_name,
    normalize_product_sku,
    product_station,
)

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000010"
UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000303"


def _alembic(database_url: str, *arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_ROOT,
        env={**os.environ, "RESTAURANTOS_DATABASE_URL": database_url},
        check=True,
        capture_output=True,
        text=True,
    )


def test_catalog_policy_is_deterministic() -> None:
    assert normalize_product_sku("  '´‘’01001 ") == "01001"
    assert is_numeric_sku("01001") is True
    assert is_numeric_sku("INV-01001") is False
    assert is_uppercase_name("CAFÉ CON LECHE") is True
    assert is_uppercase_name("Café con leche") is False
    assert product_station("BOLSA DE PAPEL", "KIWI BOX") == "packing"
    assert product_station("AGUA MINERAL", "OTROS") == "drinks"
    assert product_station("ENSALADA VERDE", "ENSALADAS") == "kitchen"
    assert canonical_inventory_item_type("PLÁSTICOS Y DESECHABLES", "ingredient") == ("packaging")


def test_catalog_cleanup_upgrade_downgrade_upgrade_roundtrip(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'catalog-cleanup.db'}"
    _alembic(database_url, "upgrade", "0026_ingredient_variations")
    engine = sa.create_engine(database_url)
    now = datetime.now(timezone.utc)

    category_rows = [
        {
            "id": "cleanup-category-legacy",
            "organization_id": ORGANIZATION_ID,
            "name": "Bebidas legado",
            "display_order": 91,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-category-food",
            "organization_id": ORGANIZATION_ID,
            "name": "ENSALADAS",
            "display_order": 92,
            "status": "archived",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-category-packing",
            "organization_id": ORGANIZATION_ID,
            "name": "SERVICIOS A DOMICILIO",
            "display_order": 93,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    ]
    product_rows = [
        {
            "id": "cleanup-product-drink",
            "organization_id": ORGANIZATION_ID,
            "category_id": "cleanup-category-legacy",
            "name": "AGUA MINERAL",
            "sku": "'01001",
            "description": None,
            "station": "unassigned",
            "status": "needs_review",
            "catalog_scope": "branch",
            "source_branch_id": BRANCH_ID,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-product-food",
            "organization_id": ORGANIZATION_ID,
            "category_id": "cleanup-category-food",
            "name": "ENSALADA VERDE",
            "sku": "02001",
            "description": None,
            "station": "unassigned",
            "status": "inactive",
            "catalog_scope": "branch",
            "source_branch_id": BRANCH_ID,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-product-packing",
            "organization_id": ORGANIZATION_ID,
            "category_id": "cleanup-category-packing",
            "name": "BOLSA DE PAPEL",
            "sku": "'03001",
            "description": None,
            "station": "kitchen",
            "status": "active",
            "catalog_scope": "branch",
            "source_branch_id": BRANCH_ID,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-product-invalid-sku",
            "organization_id": ORGANIZATION_ID,
            "category_id": "cleanup-category-food",
            "name": "PRODUCTO ANTERIOR",
            "sku": "OLD-X",
            "description": None,
            "station": "kitchen",
            "status": "active",
            "catalog_scope": "organization",
            "source_branch_id": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-product-invalid-name",
            "organization_id": ORGANIZATION_ID,
            "category_id": "cleanup-category-food",
            "name": "Producto anterior",
            "sku": "04001",
            "description": None,
            "station": "kitchen",
            "status": "active",
            "catalog_scope": "organization",
            "source_branch_id": None,
            "created_at": now,
            "updated_at": now,
        },
    ]
    item_rows = [
        {
            "id": "cleanup-item-packing",
            "organization_id": ORGANIZATION_ID,
            "name": "BOLSA",
            "sku": "1001",
            "base_unit_id": UNIT_ID,
            "item_type": "ingredient",
            "category_name": "PLASTICOS Y DESECHABLES",
            "catalog_scope": "branch",
            "source_branch_id": BRANCH_ID,
            "status": "inactive",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "cleanup-item-invalid",
            "organization_id": ORGANIZATION_ID,
            "name": "INSUMO ANTERIOR",
            "sku": "INV-OLD",
            "base_unit_id": UNIT_ID,
            "item_type": "ingredient",
            "category_name": "ABARROTE",
            "catalog_scope": "organization",
            "source_branch_id": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    ]

    with engine.begin() as connection:
        connection.execute(models.product_categories.insert(), category_rows)
        connection.execute(models.products.insert(), product_rows)
        connection.execute(models.inventory_items.insert(), item_rows)
        connection.execute(
            models.branch_product_availability.insert().values(
                branch_id=BRANCH_ID,
                product_id="cleanup-product-drink",
                is_available=False,
                updated_at=now,
            )
        )
        history_before = {
            "orders": connection.scalar(sa.select(sa.func.count(models.orders.c.id))),
            "order_lines": connection.scalar(sa.select(sa.func.count(models.order_lines.c.id))),
            "movements": connection.scalar(
                sa.select(sa.func.count(models.inventory_movements.c.id))
            ),
        }

    _alembic(database_url, "upgrade", "head")
    with engine.connect() as connection:
        products = {
            row["id"]: row
            for row in connection.execute(
                sa.select(models.products).where(models.products.c.id.like("cleanup-product-%"))
            ).mappings()
        }
        assert products["cleanup-product-drink"]["sku"] == "01001"
        assert products["cleanup-product-drink"]["station"] == "drinks"
        assert products["cleanup-product-food"]["station"] == "kitchen"
        assert products["cleanup-product-packing"]["station"] == "packing"
        for product_id in (
            "cleanup-product-drink",
            "cleanup-product-food",
            "cleanup-product-packing",
        ):
            assert products[product_id]["catalog_scope"] == "organization"
            assert products[product_id]["source_branch_id"] is None
            assert products[product_id]["status"] == "active"
        assert products["cleanup-product-invalid-sku"]["status"] == "archived"
        assert products["cleanup-product-invalid-name"]["status"] == "archived"
        assert connection.scalar(
            sa.select(models.product_categories.c.status).where(
                models.product_categories.c.id == "cleanup-category-food"
            )
        ) == "active"

        item_rows_after = {
            row["id"]: row
            for row in connection.execute(
                sa.select(models.inventory_items).where(
                    models.inventory_items.c.id.like("cleanup-item-%")
                )
            ).mappings()
        }
        assert item_rows_after["cleanup-item-packing"]["item_type"] == "packaging"
        assert item_rows_after["cleanup-item-packing"]["catalog_scope"] == "organization"
        assert item_rows_after["cleanup-item-packing"]["status"] == "active"
        assert item_rows_after["cleanup-item-invalid"]["status"] == "archived"
        assert (
            connection.scalar(
                sa.select(sa.func.count(models.branch_product_availability.c.product_id)).where(
                    models.branch_product_availability.c.product_id == "cleanup-product-drink"
                )
            )
            == 0
        )
        run = (
            connection.execute(
                sa.select(models.catalog_cleanup_runs).where(
                    models.catalog_cleanup_runs.c.revision == "0027_catalog_cleanup"
                )
            )
            .mappings()
            .one()
        )
        assert run["status"] == "completed"
        assert run["summary"]["products_archived"] >= 2
        assert (
            connection.scalar(
                sa.select(sa.func.count(models.audit_events.c.id)).where(
                    models.audit_events.c.action == "catalog.cleanup.applied"
                )
            )
            == 1
        )
        assert {
            "orders": connection.scalar(sa.select(sa.func.count(models.orders.c.id))),
            "order_lines": connection.scalar(sa.select(sa.func.count(models.order_lines.c.id))),
            "movements": connection.scalar(
                sa.select(sa.func.count(models.inventory_movements.c.id))
            ),
        } == history_before

    _alembic(database_url, "downgrade", "0026_ingredient_variations")
    with engine.connect() as connection:
        restored = (
            connection.execute(
                sa.select(models.products).where(models.products.c.id == "cleanup-product-drink")
            )
            .mappings()
            .one()
        )
        assert restored["sku"] == "'01001"
        assert restored["station"] == "unassigned"
        assert restored["status"] == "needs_review"
        assert restored["catalog_scope"] == "branch"
        assert restored["source_branch_id"] == BRANCH_ID
        assert (
            connection.scalar(
                sa.select(sa.func.count(models.branch_product_availability.c.product_id)).where(
                    models.branch_product_availability.c.product_id == "cleanup-product-drink",
                    models.branch_product_availability.c.is_available.is_(False),
                )
            )
            == 1
        )

    _alembic(database_url, "upgrade", "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                sa.select(models.products.c.sku).where(
                    models.products.c.id == "cleanup-product-drink"
                )
            )
            == "01001"
        )
    engine.dispose()

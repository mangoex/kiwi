from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.legacy_import import (
    complete_legacy_import_batch,
    create_legacy_import_batch,
    ingest_legacy_import_records,
    list_legacy_import_batches,
    list_legacy_import_records,
)
from restaurant_os.operations import (
    ADMIN_USER_ID,
    BRANCH_ID,
    BusinessError,
    add_customer_address,
    list_customers_page,
    update_product,
)
from restaurant_os.platform_data import (
    list_catalog_products,
    list_inventory_items,
    list_inventory_stock,
)
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
OTHER_BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000009999"


def migrated_session(tmp_path: Path) -> tuple[sa.Engine, Session]:
    database_path = tmp_path / "legacy-import.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=ROOT / "apps" / "api",
        env={**os.environ, "RESTAURANTOS_DATABASE_URL": database_url},
        check=True,
        capture_output=True,
        text=True,
    )
    engine = sa.create_engine(database_url)
    session = Session(engine)
    return engine, session


def test_constitucion_import_is_idempotent_scoped_and_non_operational(tmp_path: Path) -> None:
    engine, session = migrated_session(tmp_path)
    try:
        branch = (
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        session.execute(
            models.branches.insert().values(
                id=OTHER_BRANCH_ID,
                organization_id=branch["organization_id"],
                legal_entity_id=branch["legal_entity_id"],
                business_unit_id=branch["business_unit_id"],
                name="Otra sucursal",
                code="OTRA",
                timezone="America/Mazatlan",
                status="active",
                created_at=branch["created_at"],
                updated_at=branch["updated_at"],
            )
        )
        session.commit()
        movements_before = session.execute(
            sa.select(sa.func.count(models.inventory_movements.c.id))
        ).scalar_one()

        manifest_checksum = "a" * 64
        batch = create_legacy_import_batch(
            session,
            ADMIN_USER_ID,
            BRANCH_ID,
            "softrestaurant",
            manifest_checksum,
            {"files": [{"filename": "fixture.xlsx", "sha256": "b" * 64}]},
        )
        repeated_batch = create_legacy_import_batch(
            session,
            ADMIN_USER_ID,
            BRANCH_ID,
            "softrestaurant",
            manifest_checksum,
            {"files": []},
        )
        assert repeated_batch["id"] == batch["id"]

        records = [
            {
                "entity_type": "customer",
                "source_key": "C-1",
                "source_row": 6,
                "raw_payload": {"CLAVE": "C-1", "NOMBRE": "Cliente de prueba"},
                "normalized_payload": {
                    "name": "Cliente de prueba",
                    "legacy_address": "dato privado",
                },
            },
            {
                "entity_type": "inventory_item",
                "source_key": "I-1",
                "source_row": 6,
                "raw_payload": {"CLAVE": "I-1", "COSTOPROMEDIO": "123.45"},
                "normalized_payload": {
                    "sku": "I-1",
                    "name": "Insumo de prueba",
                    "category_name": "Abarrote",
                    "unit_code": "KILO",
                    "legacy_average_cost": "123.45",
                },
            },
            {
                "entity_type": "product",
                "source_key": "P-1",
                "source_row": 6,
                "raw_payload": {"CLAVE": "P-1", "PRECIO": "75.00"},
                "normalized_payload": {
                    "sku": "P-1",
                    "name": "Producto de prueba",
                    "category_name": "Bebidas",
                    "price_cents": 7500,
                },
            },
            {
                "entity_type": "presentation",
                "source_key": "PP-1",
                "source_row": 6,
                "raw_payload": {"CLAVE": "PP-1"},
                "normalized_payload": {"sku": "I-1", "supplier_code": ""},
            },
            {
                "entity_type": "recipe",
                "source_key": "R-1",
                "source_row": 6,
                "raw_payload": {"CLAVE": "R-1"},
                "normalized_payload": {"sku": "P-1", "components": []},
            },
        ]
        first = ingest_legacy_import_records(session, ADMIN_USER_ID, str(batch["id"]), records)
        second = ingest_legacy_import_records(session, ADMIN_USER_ID, str(batch["id"]), records)
        assert first["counts"] == {"imported": 2, "needs_review": 3}
        assert second["counts"] == {"unchanged": 5}
        completed = complete_legacy_import_batch(session, ADMIN_USER_ID, str(batch["id"]))
        assert completed["status"] == "review"
        assert completed["summary"] == {"imported": 2, "needs_review": 3}

        listed_batch = list_legacy_import_batches(session, ADMIN_USER_ID, BRANCH_ID)[0]
        assert listed_batch["entity_summary"] == {
            "customer": {"imported": 1},
            "inventory_item": {"imported": 1},
            "presentation": {"needs_review": 1},
            "product": {"needs_review": 1},
            "recipe": {"needs_review": 1},
        }
        product_records = list_legacy_import_records(
            session,
            ADMIN_USER_ID,
            str(batch["id"]),
            status="needs_review",
            entity_type="product",
        )
        assert product_records["total"] == 1
        assert product_records["items"][0]["normalized_payload"]["name"] == (
            "Producto de prueba"
        )
        with pytest.raises(BusinessError, match="Unsupported import entity type"):
            list_legacy_import_records(
                session,
                ADMIN_USER_ID,
                str(batch["id"]),
                entity_type="unknown",
            )

        product = (
            session.execute(sa.select(models.products).where(models.products.c.sku == "P-1"))
            .mappings()
            .one()
        )
        assert product["catalog_scope"] == "branch"
        assert product["source_branch_id"] == BRANCH_ID
        assert product["station"] == "unassigned"
        assert product["status"] == "needs_review"
        with pytest.raises(BusinessError, match="Assign a station"):
            update_product(
                session,
                str(product["id"]),
                status="active",
                actor_user_id=ADMIN_USER_ID,
            )
        update_product(
            session,
            str(product["id"]),
            category_name="Café y Matcha",
            station="drinks",
            status="active",
            actor_user_id=ADMIN_USER_ID,
        )
        activated = session.execute(
            sa.select(models.products).where(models.products.c.id == product["id"])
        ).mappings().one()
        assert activated["station"] == "drinks"
        assert activated["status"] == "active"
        branch_products = list_catalog_products(session, BRANCH_ID)
        assert any(
            row["sku"] == "P-1" and row["status"] == "active" for row in branch_products
        )
        assert not any(
            row["sku"] == "P-1" for row in list_catalog_products(session, OTHER_BRANCH_ID)
        )

        branch_items = list_inventory_items(session, BRANCH_ID)
        other_items = list_inventory_items(session, OTHER_BRANCH_ID)
        assert any(row["sku"] == "I-1" for row in branch_items)
        assert not any(row["sku"] == "I-1" for row in other_items)
        assert any(row["sku"] == "I-1" for row in list_inventory_stock(session, BRANCH_ID))
        assert not any(
            row["sku"] == "I-1" for row in list_inventory_stock(session, OTHER_BRANCH_ID)
        )
        movements_after = session.execute(
            sa.select(sa.func.count(models.inventory_movements.c.id))
        ).scalar_one()
        assert movements_after == movements_before

        branch_customers = list_customers_page(session, BRANCH_ID, "Cliente", limit=10)
        other_customers = list_customers_page(session, OTHER_BRANCH_ID, "Cliente", limit=10)
        assert branch_customers["total"] == 1
        assert other_customers["total"] == 0
        assert branch_customers["items"][0]["addresses"] == []
        assert branch_customers["items"][0]["phones"] == []
        assert branch_customers["items"][0]["legacy_address_reference"] == "dato privado"
        assert "raw_payload" not in branch_customers["items"][0]
        with pytest.raises(BusinessError, match="Active customer was not found"):
            add_customer_address(
                session,
                branch_customers["items"][0]["id"],
                {
                    "alias": "No autorizado",
                    "street": "Calle ajena",
                    "exterior_number": "1",
                    "neighborhood": "Centro",
                    "postal_code": "82000",
                    "city": "Mazatlan",
                    "municipality": "Mazatlan",
                    "state": "Sinaloa",
                },
                OTHER_BRANCH_ID,
                ADMIN_USER_ID,
            )
    finally:
        session.close()
        engine.dispose()


def test_legacy_import_migration_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-roundtrip.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    alembic("upgrade", "head")
    connection = sa.create_engine(env["RESTAURANTOS_DATABASE_URL"]).connect()
    try:
        columns = {
            column[1] for column in connection.exec_driver_sql("PRAGMA table_info(products)")
        }
        assert {"catalog_scope", "source_branch_id"} <= columns
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"legacy_import_batches", "legacy_import_records"} <= tables
    finally:
        connection.close()

    alembic("downgrade", "0024_branch_admin_scope")
    alembic("upgrade", "head")

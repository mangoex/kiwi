"""ADMIN-PROD-001 focused product configuration contracts."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import save_product_configuration
from sqlalchemy import event
from test_platform_api import (
    ADMIN_USER_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)

UTC = timezone.utc
CATEGORY_ID = "018f6f73-2d0a-74f0-8f1c-00000000a101"
GROUP_ID = "018f6f73-2d0a-74f0-8f1c-00000000a102"
VALUE_ID = "018f6f73-2d0a-74f0-8f1c-00000000a103"


def _seed_active_subgroup(client: Any) -> None:
    factory = _test_session_factory(client)
    now = datetime(2026, 9, 23, 20, 0, tzinfo=UTC)
    with factory() as session:
        session.execute(
            models.product_categories.insert().values(
                id=CATEGORY_ID,
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                name="POSTRES QA",
                display_order=99,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.category_option_groups.insert().values(
                id=GROUP_ID,
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                category_id=CATEGORY_ID,
                code="subgroup",
                name="Subgrupos",
                selection_mode="single",
                is_required=True,
                display_order=0,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.category_option_values.insert().values(
                id=VALUE_ID,
                group_id=GROUP_ID,
                code="individual",
                name="INDIVIDUAL",
                display_order=0,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "name": "PASTEL INDIVIDUAL QA",
        "sku": "99001",
        "category_id": CATEGORY_ID,
        "subgroup_option_value_id": VALUE_ID,
        "price_cents": 5500,
        "station": "kitchen",
        "image_url": None,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def test_create_product_configuration_is_atomic_and_replayable() -> None:
    client = _client_with_seeded_database()
    _seed_active_subgroup(client)
    headers = {**_admin_headers(), "Idempotency-Key": "admin-product-create-0001"}

    created = client.post(
        "/api/v1/catalog/product-configurations", headers=headers, json=_payload()
    )
    assert created.status_code == 200, created.text
    result = created.json()
    assert result["sku"] == "99001"
    assert result["station"] == "kitchen"
    assert result["subgroup"]["option_value_id"] == VALUE_ID
    assert result["price_cents"] == 5500
    assert result["updated_at"]

    replay = client.post(
        "/api/v1/catalog/product-configurations", headers=headers, json=_payload()
    )
    assert replay.status_code == 200
    assert replay.json() == result

    factory = _test_session_factory(client)
    with factory() as session:
        assert session.execute(
            sa.select(sa.func.count())
            .select_from(models.products)
            .where(models.products.c.sku == "99001")
        ).scalar_one() == 1
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.price_versions).where(
                models.price_versions.c.product_id == result["id"]
            )
        ).scalar_one() == 1
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.product_option_value_assignments).where(
                models.product_option_value_assignments.c.product_id == result["id"]
            )
        ).scalar_one() == 1
        assert session.execute(
            sa.text("SELECT COUNT(*) FROM catalog_product_configuration_commands")
        ).scalar_one() == 1

    conflict = client.post(
        "/api/v1/catalog/product-configurations",
        headers=headers,
        json=_payload(name="PASTEL DIFERENTE QA"),
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_key_conflict"


def test_invalid_subgroup_and_unknown_fields_leave_no_partial_product() -> None:
    client = _client_with_seeded_database()
    _seed_active_subgroup(client)

    invalid = client.post(
        "/api/v1/catalog/product-configurations",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-invalid-0001"},
        json=_payload(subgroup_option_value_id="018f6f73-2d0a-74f0-8f1c-00000000afff"),
    )
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["code"] == "category_option_value_group_mismatch"

    unknown = client.post(
        "/api/v1/catalog/product-configurations",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-invalid-0002"},
        json={**_payload(sku="99002"), "tax_rate": 16},
    )
    assert unknown.status_code == 422

    missing_subgroup = client.post(
        "/api/v1/catalog/product-configurations",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-invalid-0003"},
        json=_payload(sku="99003", subgroup_option_value_id=None),
    )
    assert missing_subgroup.status_code == 409
    assert missing_subgroup.json()["detail"]["code"] == "category_option_value_required"

    station_label = client.post(
        "/api/v1/catalog/product-configurations",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-invalid-0004"},
        json=_payload(sku="99004", station="1 - BEBIDAS"),
    )
    assert station_label.status_code == 422

    legacy_unknown = client.post(
        "/api/v1/catalog/products",
        headers=_admin_headers(),
        json={
            "name": "PRODUCTO LEGACY QA",
            "sku": "99006",
            "category_name": "POSTRES QA",
            "price_cents": 5500,
            "station": "kitchen",
            "tax_rate": 16,
        },
    )
    assert legacy_unknown.status_code == 422
    assert legacy_unknown.json()["detail"]["code"] == "product_fields_unsupported"

    factory = _test_session_factory(client)
    with factory() as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.products).where(
                models.products.c.sku.in_(["99001", "99002"])
            )
        ).scalar_one() == 0


def test_update_requires_observed_version_and_does_not_duplicate_unchanged_price() -> None:
    client = _client_with_seeded_database()
    _seed_active_subgroup(client)
    create_headers = {**_admin_headers(), "Idempotency-Key": "admin-product-create-0003"}
    result = client.post(
        "/api/v1/catalog/product-configurations", headers=create_headers, json=_payload(sku="99003")
    ).json()

    update_payload = {
        **_payload(sku="99003", name="PASTEL INDIVIDUAL ACTUALIZADO"),
        "expected_updated_at": result["updated_at"],
    }
    updated = client.put(
        f"/api/v1/catalog/product-configurations/{result['id']}",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-update-0001"},
        json=update_payload,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "PASTEL INDIVIDUAL ACTUALIZADO"

    stale = client.put(
        f"/api/v1/catalog/product-configurations/{result['id']}",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-update-0002"},
        json={**update_payload, "name": "OTRA EDICION"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "product_configuration_version_conflict"

    factory = _test_session_factory(client)
    with factory() as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.price_versions).where(
                models.price_versions.c.product_id == result["id"]
            )
        ).scalar_one() == 1


def test_pos_preview_uses_real_projection_without_writes() -> None:
    client = _client_with_seeded_database()
    _seed_active_subgroup(client)
    created = client.post(
        "/api/v1/catalog/product-configurations",
        headers={**_admin_headers(), "Idempotency-Key": "admin-product-create-0004"},
        json=_payload(sku="99004"),
    ).json()
    factory = _test_session_factory(client)
    with factory() as session:
        before_orders = session.execute(
            sa.select(sa.func.count()).select_from(models.orders)
        ).scalar_one()
        before_availability = session.execute(
            sa.select(sa.func.count()).select_from(models.branch_product_availability)
        ).scalar_one()

    preview = client.get(
        f"/api/v1/catalog/products/{created['id']}/pos-preview"
        "?branch_id=018f6f73-2d0a-74f0-8f1c-000000000003",
        headers=_admin_headers(),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["eligible"] is True
    assert preview.json()["subgroup"]["option_value_id"] == VALUE_ID

    with factory() as session:
        assert (
            session.execute(sa.select(sa.func.count()).select_from(models.orders)).scalar_one()
            == before_orders
        )
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.branch_product_availability)
        ).scalar_one() == before_availability


def test_failure_between_price_and_subgroup_rolls_back_every_write() -> None:
    client = _client_with_seeded_database()
    _seed_active_subgroup(client)
    factory = _test_session_factory(client)
    with factory() as session:
        engine = session.get_bind()

        def fail_assignment(
            _conn: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: Any,
        ) -> None:
            if "INSERT INTO product_option_value_assignments" in statement:
                raise RuntimeError("injected subgroup write failure")

        event.listen(engine, "before_cursor_execute", fail_assignment)
        try:
            with pytest.raises(RuntimeError, match="injected subgroup"):
                save_product_configuration(
                    session,
                    _payload(sku="99005"),
                    "admin-product-rollback-0001",
                    ADMIN_USER_ID,
                )
        finally:
            event.remove(engine, "before_cursor_execute", fail_assignment)

    with factory() as session:
        assert session.execute(
            sa.select(sa.func.count())
            .select_from(models.products)
            .where(models.products.c.sku == "99005")
        ).scalar_one() == 0
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.catalog_product_configuration_commands).where(
                models.catalog_product_configuration_commands.c.idempotency_key
                == "admin-product-rollback-0001"
            )
        ).scalar_one() == 0


def test_admin_product_migration_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "admin-product-migration.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    alembic("upgrade", "0068_admin_product_configuration")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0068_admin_product_configuration",
        )
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='catalog_product_configuration_commands'"
        ).fetchone() == ("catalog_product_configuration_commands",)
    alembic("downgrade", "0067_offline_orders")
    alembic("upgrade", "0068_admin_product_configuration")

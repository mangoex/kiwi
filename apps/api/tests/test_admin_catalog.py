"""Focused ADMIN-RETRO-001 contracts against the real SQLite domain boundary."""

from __future__ import annotations

import logging
from collections.abc import Generator
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.admin_catalog import (
    get_category_priorities,
    get_recipe_usages,
    get_stock_thresholds,
    preview_bulk_recipe,
    set_category_priorities,
    set_stock_threshold,
)
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import AuthorizationError, BusinessError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from test_cash_concepts import OWNER_ID, OWNER_ROLE_ID, _seed_cash_concept_scope
from test_cash_ledger import BRANCH_A, CASHIER_ID, CASHIER_ROLE_ID, NOW, ORG_ID, _new_session
from test_pco007_recipe_reports import ITEM_ID, PRODUCT_ID, UNIT_ID, _seed_recipe_scope

CATEGORY_A = "018f6f73-2d0a-74f0-8f1c-000000009101"
CATEGORY_B = "018f6f73-2d0a-74f0-8f1c-000000009102"
CATEGORY_C = "018f6f73-2d0a-74f0-8f1c-000000009105"
PRODUCT_B = "018f6f73-2d0a-74f0-8f1c-000000009103"
WAREHOUSE_A = "018f6f73-2d0a-74f0-8f1c-000000009104"
FOREIGN_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000009107"


def _seed_admin_catalog_scope(session) -> None:
    _seed_recipe_scope(session)
    session.execute(
        models.warehouses.insert().values(
            id=WAREHOUSE_A,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            name="Almacén Centro",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    for code in ("catalog.manage", "inventory.read"):
        permission_id = f"permission-{code}"
        session.execute(
            models.permissions.insert().values(
                id=permission_id, code=code, description=code, created_at=NOW
            )
        )
        role_ids = (
            (OWNER_ROLE_ID, CASHIER_ROLE_ID) if code == "catalog.manage" else (CASHIER_ROLE_ID,)
        )
        for role_id in role_ids:
            session.execute(
                models.role_permissions.insert().values(
                    role_id=role_id, permission_id=permission_id
                )
            )
    session.execute(
        models.product_categories.insert().values(
            id=CATEGORY_A,
            organization_id=ORG_ID,
            name="Bebidas retro",
            display_order=2,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.product_categories.insert().values(
            id=CATEGORY_B,
            organization_id=ORG_ID,
            name="Comida retro",
            display_order=3,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.products.insert().values(
            id=PRODUCT_B,
            organization_id=ORG_ID,
            category_id=CATEGORY_B,
            name="Producto B",
            sku="PCO007-B",
            description=None,
            station="kitchen",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.commit()


def _recipe_payload() -> dict[str, object]:
    return {
        "yield_quantity": "1",
        "yield_unit_id": UNIT_ID,
        "components": [
            {"item_id": ITEM_ID, "unit_id": UNIT_ID, "net_quantity": "1", "waste_rate": "0"}
        ],
    }


def _client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        _seed_cash_concept_scope(session)
        _seed_admin_catalog_scope(session)
    app = create_app()

    def override() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_priorities_are_complete_and_independent() -> None:
    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        initial = get_category_priorities(session, OWNER_ID)
        ids = [row["id"] for row in initial["view_order"]]
        assert ids == ["018f6f73-2d0a-74f0-8f1c-000000007705", CATEGORY_A, CATEGORY_B]
        changed = set_category_priorities(
            session,
            OWNER_ID,
            view_category_ids=ids,
            print_category_ids=list(reversed(ids)),
            expected_version=initial["version"],
        )
        assert [row["id"] for row in changed["view_order"]] == ids
        assert [row["id"] for row in changed["print_order"]] == list(reversed(ids))
        with pytest.raises(BusinessError, match="exactly once"):
            set_category_priorities(
                session,
                OWNER_ID,
                view_category_ids=ids[:-1],
                print_category_ids=list(reversed(ids)),
                expected_version=changed["version"],
            )
        preserved = get_category_priorities(session, OWNER_ID)
        assert preserved["version"] == changed["version"]
        session.execute(
            models.product_categories.update()
            .where(models.product_categories.c.id == CATEGORY_B)
            .values(status="archived")
        )
        session.execute(
            models.product_categories.insert().values(
                id=CATEGORY_C,
                organization_id=ORG_ID,
                name="Postres retro",
                display_order=4,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
        reconciled = get_category_priorities(session, OWNER_ID)
        expected_active = [ids[0], CATEGORY_A, CATEGORY_C]
        assert [row["id"] for row in reconciled["view_order"]] == expected_active
        assert [row["id"] for row in reconciled["print_order"]] == [
            CATEGORY_A,
            ids[0],
            CATEGORY_C,
        ]
    finally:
        session.close()
        engine.dispose()


def test_thresholds_use_theoretical_ledger_stock_without_writing_movements() -> None:
    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        warehouse_id = (
            session.execute(
                models.warehouses.select().where(models.warehouses.c.branch_id == BRANCH_A)
            )
            .mappings()
            .one()["id"]
        )
        before = session.execute(models.inventory_movements.select()).all()
        saved = set_stock_threshold(
            session,
            CASHIER_ID,
            BRANCH_A,
            ITEM_ID,
            minimum_quantity=Decimal("2"),
            maximum_quantity=Decimal("4"),
            expected_version=None,
        )
        assert saved["minimum_quantity"] == Decimal("2.000000")
        assert session.execute(models.inventory_movements.select()).all() == before
        rows = get_stock_thresholds(session, CASHIER_ID, BRANCH_A)
        row = next(value for value in rows if value["item_id"] == ITEM_ID)
        assert row["warehouse_id"] == warehouse_id
        assert row["status"] == "below_minimum"
        for value, code in (
            ("1e100", "stock_threshold_range_invalid"),
            ("999999999999.000001", "stock_threshold_range_invalid"),
            ("0.0000004", "stock_threshold_precision_invalid"),
        ):
            with pytest.raises(BusinessError) as error:
                set_stock_threshold(
                    session,
                    CASHIER_ID,
                    BRANCH_A,
                    ITEM_ID,
                    minimum_quantity=value,
                    maximum_quantity="4",
                    expected_version=saved["version"],
                )
            assert error.value.code == code
        with pytest.raises(BusinessError) as error:
            set_stock_threshold(
                session,
                CASHIER_ID,
                BRANCH_A,
                ITEM_ID,
                minimum_quantity="1.0000004",
                maximum_quantity="1.0000003",
                expected_version=saved["version"],
            )
        assert error.value.code == "stock_threshold_precision_invalid"
        assert get_stock_thresholds(session, CASHIER_ID, BRANCH_A)[0]["version"] == saved["version"]
    finally:
        session.close()
        engine.dispose()


def test_threshold_projection_excludes_reservation_movements() -> None:
    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        threshold = set_stock_threshold(
            session,
            CASHIER_ID,
            BRANCH_A,
            ITEM_ID,
            minimum_quantity="0",
            maximum_quantity="1",
            expected_version=None,
        )
        session.execute(
            models.inventory_movements.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009106",
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                warehouse_id=WAREHOUSE_A,
                item_id=ITEM_ID,
                movement_type="SALE_RESERVATION",
                quantity_delta=Decimal("-5"),
                unit_id=UNIT_ID,
                unit_cost=Decimal("0"),
                total_cost=Decimal("0"),
                effective_at=NOW,
                actor_user_id=CASHIER_ID,
                document_type="order",
                document_id="reservation-order",
                reference="admin-retro-test",
                reason="test reservation",
                notes=None,
                idempotency_key="admin-retro-reservation",
                status="confirmed",
                reversal_of_id=None,
                source_type="order_acceptance",
                source_id="reservation-order",
                created_at=NOW,
            )
        )
        session.commit()
        row = next(
            value
            for value in get_stock_thresholds(session, CASHIER_ID, BRANCH_A)
            if value["item_id"] == ITEM_ID
        )
        assert threshold["version"] == 1
        assert row["quantity_on_hand"] == Decimal("0.000000")
        assert row["status"] == "in_range"
    finally:
        session.close()
        engine.dispose()


def test_preview_is_read_only_and_effective_usage_prefers_local_recipe() -> None:
    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        preview = preview_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID, PRODUCT_B],
            payload=_recipe_payload(),
        )
        assert len(preview["destinations"]) == 2
        assert session.execute(models.recipes.select()).all() == []
        assert preview["fingerprint"]
        assert preview["destinations"][0]["difference"]["changed"] is True
        assert preview["destinations"][0]["difference"]["current_components"] == []
        difference = preview["destinations"][0]["difference"]
        assert difference["next_components"][0]["net_quantity"] == Decimal("1.000000")
        # A local recipe must hide the central fallback when uses are resolved.
        from restaurant_os.operations import update_product_recipe_versioned

        local = update_product_recipe_versioned(
            session, PRODUCT_ID, _recipe_payload(), BRANCH_A, None, "local-usage", CASHIER_ID
        )
        usages = get_recipe_usages(session, CASHIER_ID, ITEM_ID, BRANCH_A)
        assert len(usages) == 1
        usage = usages[0]
        assert usage["product_id"] == PRODUCT_ID
        assert usage["recipe_id"] == local["id"]
        assert usage["recipe_version"] == 1
        assert usage["item_id"] == ITEM_ID
        assert usage["quantity_base_units"] == Decimal("1.000000")
        assert usage["unit_id"] == UNIT_ID
        assert usage["product_name"]
        assert usage["product_sku"]
        assert usage["unit_code"]
    finally:
        session.close()
        engine.dispose()


def test_bulk_apply_replays_without_extra_recipe_versions() -> None:
    from restaurant_os.admin_catalog import apply_bulk_recipe

    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        preview = preview_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID, PRODUCT_B],
            payload=_recipe_payload(),
        )
        expected = {
            row["product_id"]: row["expected_active_recipe_id"] for row in preview["destinations"]
        }
        created = apply_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID, PRODUCT_B],
            payload=_recipe_payload(),
            preview_fingerprint=preview["fingerprint"],
            expected_active_recipe_ids=expected,
            idempotency_key="admin-retro-bulk-1",
        )
        replay = apply_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID, PRODUCT_B],
            payload=_recipe_payload(),
            preview_fingerprint=preview["fingerprint"],
            expected_active_recipe_ids=expected,
            idempotency_key="admin-retro-bulk-1",
        )
        assert replay == created
        assert len(created["destinations"]) == 2
        assert session.execute(models.recipes.select()).mappings().all()
        assert session.execute(models.inventory_movements.select()).all() == []
        session.execute(
            models.products.update()
            .where(models.products.c.id == PRODUCT_B)
            .values(status="archived")
        )
        session.commit()
        replay_after_archive = apply_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID, PRODUCT_B],
            payload=_recipe_payload(),
            preview_fingerprint=preview["fingerprint"],
            expected_active_recipe_ids=expected,
            idempotency_key="admin-retro-bulk-1",
        )
        assert replay_after_archive == created
    finally:
        session.close()
        engine.dispose()


def test_bulk_apply_rolls_back_every_destination_when_second_write_fails() -> None:
    from restaurant_os.admin_catalog import apply_bulk_recipe

    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        preview = preview_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID, PRODUCT_B],
            payload=_recipe_payload(),
        )
        expected = {
            row["product_id"]: row["expected_active_recipe_id"] for row in preview["destinations"]
        }
        inserts = 0

        def fail_second_component(
            _connection, _cursor, statement, _parameters, _context, _executemany
        ) -> None:
            nonlocal inserts
            if statement.startswith("INSERT INTO recipe_components"):
                inserts += 1
                if inserts == 2:
                    raise RuntimeError("injected component failure")

        sa.event.listen(engine, "before_cursor_execute", fail_second_component)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                apply_bulk_recipe(
                    session,
                    CASHIER_ID,
                    branch_id=BRANCH_A,
                    destination_product_ids=[PRODUCT_ID, PRODUCT_B],
                    payload=_recipe_payload(),
                    preview_fingerprint=preview["fingerprint"],
                    expected_active_recipe_ids=expected,
                    idempotency_key="admin-retro-rollback",
                )
        finally:
            sa.event.remove(engine, "before_cursor_execute", fail_second_component)
        assert session.execute(models.recipes.select()).all() == []
        assert session.execute(models.admin_recipe_bulk_commands.select()).all() == []
    finally:
        session.close()
        engine.dispose()


def test_catalog_telemetry_is_structured_and_usage_rejects_foreign_branch_item(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from restaurant_os.admin_catalog import apply_bulk_recipe

    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        caplog.set_level(logging.INFO, logger="restaurant_os.admin_catalog")
        preview = preview_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID],
            payload=_recipe_payload(),
        )
        expected = {
            row["product_id"]: row["expected_active_recipe_id"] for row in preview["destinations"]
        }
        created = apply_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID],
            payload=_recipe_payload(),
            preview_fingerprint=preview["fingerprint"],
            expected_active_recipe_ids=expected,
            idempotency_key="admin-retro-telemetry",
        )
        assert apply_bulk_recipe(
            session,
            CASHIER_ID,
            branch_id=BRANCH_A,
            destination_product_ids=[PRODUCT_ID],
            payload=_recipe_payload(),
            preview_fingerprint=preview["fingerprint"],
            expected_active_recipe_ids=expected,
            idempotency_key="admin-retro-telemetry",
        ) == created
        with pytest.raises(BusinessError):
            apply_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_ID],
                payload=_recipe_payload(),
                preview_fingerprint=preview["fingerprint"],
                expected_active_recipe_ids={},
                idempotency_key="admin-retro-telemetry",
            )
        session.execute(
            models.inventory_items.insert().values(
                id=FOREIGN_ITEM_ID,
                organization_id=ORG_ID,
                name="Insumo local ajeno",
                sku="FOREIGN-ITEM",
                base_unit_id=UNIT_ID,
                item_type="ingredient",
                catalog_scope="branch",
                source_branch_id="018f6f73-2d0a-74f0-8f1c-000000000013",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
        with pytest.raises(BusinessError, match="not found"):
            get_recipe_usages(session, CASHIER_ID, FOREIGN_ITEM_ID, BRANCH_A)
        with pytest.raises(AuthorizationError):
            get_recipe_usages(session, "not-an-actor", ITEM_ID, BRANCH_A)
        records = [
            record
            for record in caplog.records
            if getattr(record, "metric", "").startswith("admin_catalog.")
        ]
        assert {record.result for record in records} >= {
            "success",
            "replay",
            "conflict",
            "denied",
            "error",
        }
        bulk_success = next(
            record
            for record in records
            if record.metric == "admin_catalog.bulk_recipe" and record.result == "success"
        )
        assert bulk_success.command_id == created["command_id"]
        assert bulk_success.destination_count == 1
        assert bulk_success.duration_ms >= 0
        assert all(
            not {"product_id", "item_id", "actor_user_id", "payload", "email"}
            & set(record.__dict__)
            for record in records
        )
    finally:
        session.close()
        engine.dispose()


def test_admin_catalog_http_boundary_is_strict_and_uses_server_scope() -> None:
    client = _client()
    owner_headers = {"X-Actor-User-Id": OWNER_ID}
    response = client.get("/api/v1/admin-catalog/category-priorities", headers=owner_headers)
    assert response.status_code == 200
    priorities = response.json()
    category_ids = [row["id"] for row in priorities["view_order"]]
    update = client.put(
        "/api/v1/admin-catalog/category-priorities",
        headers=owner_headers,
        json={
            "expected_version": priorities["version"],
            "view_category_ids": category_ids,
            "print_category_ids": list(reversed(category_ids)),
            "organization_id": "forged",
        },
    )
    assert update.status_code == 422
    allowed = client.put(
        "/api/v1/admin-catalog/category-priorities",
        headers=owner_headers,
        json={
            "expected_version": priorities["version"],
            "view_category_ids": category_ids,
            "print_category_ids": list(reversed(category_ids)),
        },
    )
    assert allowed.status_code == 200
    threshold = client.put(
        f"/api/v1/admin-catalog/stock-thresholds/{ITEM_ID}?branch_id={BRANCH_A}",
        headers={"X-Actor-User-Id": CASHIER_ID},
        json={"minimum_quantity": "1.25", "maximum_quantity": "2.50", "expected_version": None},
    )
    assert threshold.status_code == 200
    assert threshold.json()["minimum_quantity"] == "1.250000"


def test_threshold_rejects_stale_version_and_bulk_payload_rejects_invalid_units_and_waste() -> None:
    engine, session = _new_session()
    try:
        _seed_admin_catalog_scope(session)
        first = set_stock_threshold(
            session,
            CASHIER_ID,
            BRANCH_A,
            ITEM_ID,
            minimum_quantity="1",
            maximum_quantity="2",
            expected_version=None,
        )
        second = set_stock_threshold(
            session,
            CASHIER_ID,
            BRANCH_A,
            ITEM_ID,
            minimum_quantity="2",
            maximum_quantity="3",
            expected_version=first["version"],
        )
        assert second["version"] == 2
        with pytest.raises(BusinessError, match="changed"):
            set_stock_threshold(
                session,
                CASHIER_ID,
                BRANCH_A,
                ITEM_ID,
                minimum_quantity="3",
                maximum_quantity="4",
                expected_version=first["version"],
            )
        invalid_waste = _recipe_payload()
        invalid_waste["components"] = [
            {"item_id": ITEM_ID, "unit_id": UNIT_ID, "net_quantity": "1", "waste_rate": "1"}
        ]
        with pytest.raises(BusinessError, match="waste"):
            preview_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_ID],
                payload=invalid_waste,
            )
        invalid_unit = _recipe_payload()
        invalid_unit["components"] = [
            {
                "item_id": ITEM_ID,
                "unit_id": "018f6f73-2d0a-74f0-8f1c-000000009999",
                "net_quantity": "1",
                "waste_rate": "0",
            }
        ]
        with pytest.raises(BusinessError, match="incompatible"):
            preview_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_ID],
                payload=invalid_unit,
            )
    finally:
        session.close()
        engine.dispose()

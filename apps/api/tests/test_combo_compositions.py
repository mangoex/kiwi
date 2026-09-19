"""TDD-TS-112: fixed combo composition contracts."""

from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.combo import effective_composition, save_composition
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import (
    BusinessError,
    advance_kds_task,
    amend_order,
    cancel_order,
    create_local_order,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from test_cash_concepts import OWNER_ID, OWNER_ROLE_ID
from test_cash_ledger import BRANCH_A, BRANCH_B, NOW, ORG_ID, _new_session

ACTOR = OWNER_ID
CATEGORY = "018f6f73-2d0a-74f0-8f1c-000000009301"
COMBO = "018f6f73-2d0a-74f0-8f1c-000000009302"
BURGER = "018f6f73-2d0a-74f0-8f1c-000000009303"
DRINK = "018f6f73-2d0a-74f0-8f1c-000000009304"


def _seed(session) -> None:
    session.execute(
        models.permissions.insert().values(
            id="combo-recipes-manage",
            code="recipes.manage",
            description="recipes.manage",
            created_at=NOW,
        )
    )
    session.execute(
        models.role_permissions.insert().values(
            role_id=OWNER_ROLE_ID, permission_id="combo-recipes-manage"
        )
    )
    session.execute(
        models.product_categories.insert().values(
            id=CATEGORY,
            organization_id=ORG_ID,
            name="Combos",
            display_order=1,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    for product_id, name, station in (
        (COMBO, "Combo fijo", "packing"),
        (BURGER, "Hamburguesa", "kitchen"),
        (DRINK, "Refresco", "beverages"),
    ):
        session.execute(
            models.products.insert().values(
                id=product_id,
                organization_id=ORG_ID,
                category_id=CATEGORY,
                name=name,
                sku=product_id[-4:],
                station=station,
                status="active",
                catalog_scope="organization",
                source_branch_id=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.execute(
        models.price_versions.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000009305",
            organization_id=ORG_ID,
            product_id=COMBO,
            price_cents=15900,
            currency="MXN",
            valid_from=NOW,
            valid_to=None,
            created_at=NOW,
        )
    )
    session.commit()


def _seed_combo_recipes_and_order_scope(session) -> None:
    unit_id = "018f6f73-2d0a-74f0-8f1c-000000009306"
    item_id = "018f6f73-2d0a-74f0-8f1c-000000009307"
    for permission_id, code in (
        ("combo-orders-create", "orders.create"),
        ("combo-orders-read", "orders.read"),
        ("combo-orders-amend", "orders.amend"),
        ("combo-orders-cancel", "orders.cancel"),
    ):
        session.execute(
            models.permissions.insert().values(
                id=permission_id, code=code, description=code, created_at=NOW
            )
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=OWNER_ROLE_ID, permission_id=permission_id
            )
        )
    session.execute(
        models.warehouses.insert().values(
            id="combo-warehouse",
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            name="Almacén combo",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.inventory_units.insert().values(
            id=unit_id,
            organization_id=ORG_ID,
            code="pz",
            name="Pieza",
            precision_scale=3,
            created_at=NOW,
        )
    )
    session.execute(
        models.inventory_items.insert().values(
            id=item_id,
            organization_id=ORG_ID,
            name="Insumo combo",
            sku="COMBO-I",
            base_unit_id=unit_id,
            item_type="ingredient",
            catalog_scope="organization",
            source_branch_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    for index, product_id in enumerate((BURGER, DRINK), start=1):
        recipe_id = f"018f6f73-2d0a-74f0-8f1c-00000000930{7 + index}"
        session.execute(
            models.recipes.insert().values(
                id=recipe_id,
                organization_id=ORG_ID,
                product_id=product_id,
                output_item_id=None,
                branch_id=None,
                recipe_type="sale",
                version=1,
                status="active",
                yield_quantity=Decimal("1"),
                yield_unit_id=unit_id,
                valid_from=NOW,
                valid_to=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.recipe_components.insert().values(
                recipe_id=recipe_id,
                item_id=item_id,
                quantity_base_units=Decimal("0.250"),
                unit_id=unit_id,
                net_quantity=Decimal("0.250"),
                waste_rate=Decimal("0"),
                gross_quantity=Decimal("0.250"),
                sort_order=1,
                notes=None,
            )
        )
    session.commit()


def test_composition_is_versioned_scoped_and_uses_combo_price() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        saved = save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=0,
            idempotency_key="combo-v1",
            components=[
                {"product_id": BURGER, "quantity": "1"},
                {"product_id": DRINK, "quantity": Decimal("2")},
            ],
        )
        assert saved["version"] == 1
        assert saved["price_cents"] == 15900
        assert [component["product_id"] for component in saved["components"]] == [BURGER, DRINK]
        effective = effective_composition(session, COMBO, BRANCH_A)
        assert effective["version"] == 1
        with pytest.raises(BusinessError, match="Nested"):
            save_composition(
                session,
                ACTOR,
                BURGER,
                None,
                expected_version=0,
                idempotency_key="nested",
                components=[{"product_id": COMBO, "quantity": "1"}],
            )
        with pytest.raises(BusinessError, match="positive"):
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=1,
                idempotency_key="bad",
                components=[{"product_id": BURGER, "quantity": "NaN"}],
            )
        with pytest.raises(BusinessError, match="whole product unit"):
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=1,
                idempotency_key="fractional",
                components=[{"product_id": BURGER, "quantity": "0.5"}],
            )
        with pytest.raises(BusinessError, match="precision"):
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=1,
                idempotency_key="huge-exponent",
                components=[{"product_id": BURGER, "quantity": "1e999999"}],
            )
        with pytest.raises(BusinessError, match="180"):
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=1,
                idempotency_key="x" * 181,
                components=[{"product_id": BURGER, "quantity": "1"}],
            )
        assert effective_composition(session, COMBO, BRANCH_A)["version"] == 1
    finally:
        session.close()
        engine.dispose()


def test_amendment_replaces_combo_with_new_component_snapshots() -> None:
    engine, session = _new_session()
    try:
        # The real capture and restore path must satisfy the task/snapshot FK,
        # not merely the migration fixture where FKs stay off to seed history.
        session.execute(sa.text("PRAGMA foreign_keys = ON"))
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=0,
            idempotency_key="combo-amend-version-001",
            components=[
                {"product_id": BURGER, "quantity": "1"},
                {"product_id": DRINK, "quantity": "1"},
            ],
        )
        order = create_local_order(
            session,
            [{"product_id": COMBO, "quantity": 1}],
            register_id="CAJA-01",
            actor_user_id=ACTOR,
            idempotency_key="combo-amend-create-001",
        )
        old_line_id = order["lines"][0]["id"]
        amended = amend_order(
            session,
            order["id"],
            [{"product_id": COMBO, "quantity": 2}],
            expected_version=1,
            idempotency_key="combo-amend-apply-001",
            actor_user_id=ACTOR,
        )
        active_line = next(line for line in amended["lines"] if line["status"] == "active")
        assert active_line["id"] != old_line_id
        assert active_line["line_total_cents"] == 31800
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(models.order_line_component_snapshots)
                .where(models.order_line_component_snapshots.c.order_line_id == active_line["id"])
            ).scalar_one()
            == 2
        )
        assert (
            session.execute(
                sa.select(models.order_line_consumption_snapshots.c.order_line_id).where(
                    models.order_line_consumption_snapshots.c.order_line_id == old_line_id
                )
            ).scalar_one()
            == old_line_id
        )
    finally:
        session.close()
        engine.dispose()


def test_replay_is_idempotent_and_local_scope_precedes_corporate() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        first = save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=0,
            idempotency_key="replay",
            components=[{"product_id": BURGER, "quantity": "1"}],
        )
        assert (
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=0,
                idempotency_key="replay",
                components=[{"product_id": BURGER, "quantity": "1"}],
            )
            == first
        )
        session.execute(
            models.products.update()
            .where(models.products.c.id == BURGER)
            .values(status="archived")
        )
        session.commit()
        assert (
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=0,
                idempotency_key="replay",
                components=[{"product_id": BURGER, "quantity": "1"}],
            )
            == first
        )
        session.execute(
            models.products.update()
            .where(models.products.c.id == BURGER)
            .values(status="active")
        )
        session.execute(
            models.price_versions.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009396",
                organization_id=ORG_ID,
                product_id=BURGER,
                price_cents=9900,
                currency="MXN",
                valid_from=NOW,
                valid_to=None,
                created_at=NOW,
            )
        )
        session.commit()
        save_composition(
            session,
            ACTOR,
            BURGER,
            None,
            expected_version=0,
            idempotency_key="burger-became-combo",
            components=[{"product_id": DRINK, "quantity": "1"}],
        )
        assert (
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=0,
                idempotency_key="replay",
                components=[{"product_id": BURGER, "quantity": "1"}],
            )
            == first
        )
        with pytest.raises(BusinessError, match="payload"):
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=1,
                idempotency_key="replay",
                components=[{"product_id": DRINK, "quantity": "1"}],
            )
        local = save_composition(
            session,
            ACTOR,
            COMBO,
            BRANCH_A,
            expected_version=0,
            idempotency_key="local",
            components=[{"product_id": DRINK, "quantity": "1"}],
        )
        assert effective_composition(session, COMBO, BRANCH_A)["id"] == local["id"]
    finally:
        session.close()
        engine.dispose()


def test_nested_combo_guard_uses_the_requested_effective_scope() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        session.execute(
            models.price_versions.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009399",
                organization_id=ORG_ID,
                product_id=BURGER,
                price_cents=9900,
                currency="MXN",
                valid_from=NOW,
                valid_to=None,
                created_at=NOW,
            )
        )
        session.commit()
        north = save_composition(
            session,
            ACTOR,
            BURGER,
            BRANCH_B,
            expected_version=0,
            idempotency_key="north-burger-combo",
            components=[{"product_id": DRINK, "quantity": "1"}],
        )
        assert north["branch_id"] == BRANCH_B
        centro = save_composition(
            session,
            ACTOR,
            COMBO,
            BRANCH_A,
            expected_version=0,
            idempotency_key="centro-combo-fixed",
            components=[{"product_id": BURGER, "quantity": "1"}],
        )
        assert centro["branch_id"] == BRANCH_A
    finally:
        session.close()
        engine.dispose()


def test_composition_http_contract_is_strict_and_returns_scope_versions() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        from test_cash_concepts import _seed_cash_concept_scope

        _seed_cash_concept_scope(session)
        _seed(session)
    app = create_app()

    def override() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    headers = {"X-Actor-User-Id": ACTOR, "Idempotency-Key": "combo-http-contract-001"}
    # This actor has recipes.manage from _seed but no POS permission.  The
    # composer therefore reads the catalog without the POS-only branch query
    # and applies its branch scope using catalog metadata.
    assert client.get("/api/v1/catalog/products", headers=headers).status_code == 200
    assert (
        client.get(f"/api/v1/catalog/products?branch_id={BRANCH_A}", headers=headers).status_code
        == 403
    )
    response = client.put(
        f"/api/v1/products/{COMBO}/composition",
        headers=headers,
        json={
            "branch_id": None,
            "expected_version": 0,
            "components": [{"product_id": BURGER, "quantity": "1"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["price_cents"] == 15900
    assert response.json()["components"][0]["name"] == "Hamburguesa"
    detail = client.get(f"/api/v1/products/{COMBO}/composition", headers={"X-Actor-User-Id": ACTOR})
    assert detail.status_code == 200
    assert detail.json()["expected_version"] == 1
    assert detail.json()["product"]["is_combo"] is True
    second = client.put(
        f"/api/v1/products/{COMBO}/composition",
        headers={"X-Actor-User-Id": ACTOR, "Idempotency-Key": "combo-http-contract-v2"},
        json={
            "branch_id": None,
            "expected_version": 1,
            "components": [{"product_id": DRINK, "quantity": "1"}],
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] != response.json()["id"]
    replay = client.put(
        f"/api/v1/products/{COMBO}/composition",
        headers=headers,
        json={
            "branch_id": None,
            "expected_version": 0,
            "components": [{"product_id": BURGER, "quantity": "1"}],
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == response.json()["id"]
    assert replay.json()["components"][0]["name"] == "Hamburguesa"
    bad = client.put(
        f"/api/v1/products/{COMBO}/composition",
        headers={"X-Actor-User-Id": ACTOR, "Idempotency-Key": "combo-http-contract-002"},
        json={
            "branch_id": None,
            "expected_version": 1,
            "components": [{"product_id": BURGER, "quantity": 1}],
        },
    )
    assert bad.status_code == 422
    engine.dispose()


def test_two_combo_units_freeze_components_and_consume_after_both_stations() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        session.execute(
            models.inventory_cost_states.insert().values(
                branch_id=BRANCH_A,
                warehouse_id="combo-warehouse",
                item_id="018f6f73-2d0a-74f0-8f1c-000000009307",
                quantity_on_hand=Decimal("10"),
                average_unit_cost=Decimal("10.000000"),
                last_unit_cost=Decimal("10.000000"),
                last_supplier_id=None,
                last_cost_at=None,
                updated_at=NOW,
            )
        )
        session.commit()
        save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=0,
            idempotency_key="combo-order-version-001",
            components=[
                {"product_id": BURGER, "quantity": "1"},
                {"product_id": DRINK, "quantity": "1"},
            ],
        )
        order = create_local_order(
            session,
            [{"product_id": COMBO, "quantity": 2}],
            register_id="CAJA-01",
            actor_user_id=ACTOR,
            idempotency_key="combo-order-create-001",
        )
        assert order["total_cents"] == 31800
        assert len(order["production_tasks"]) == 2
        assert {task["station"] for task in order["production_tasks"]} == {"kitchen", "beverages"}
        line_id = order["lines"][0]["id"]
        component_rows = (
            session.execute(
                sa.select(models.order_line_component_snapshots).where(
                    models.order_line_component_snapshots.c.order_line_id == line_id
                )
            )
            .mappings()
            .all()
        )
        assert {row["component_product_id"] for row in component_rows} == {BURGER, DRINK}
        assert {row["composition_version"] for row in component_rows} == {1}
        assert {row["recipe_version"] for row in component_rows} == {1}
        assert {Decimal(str(row["component_quantity"])) for row in component_rows} == {
            Decimal("2.000000")
        }
        assert {
            Decimal(str(component["gross_quantity"]))
            for row in component_rows
            for component in row["recipe_components"]
        } == {Decimal("0.500000")}
        assert {
            Decimal(str(component["unit_cost"]))
            for row in component_rows
            for component in row["recipe_components"]
        } == {Decimal("10.000000")}
        assert {
            Decimal(str(component["total_cost"]))
            for row in component_rows
            for component in row["recipe_components"]
        } == {Decimal("5.000000")}
        aggregate = (
            session.execute(
                sa.select(models.order_line_consumption_snapshots).where(
                    models.order_line_consumption_snapshots.c.order_line_id == line_id
                )
            )
            .mappings()
            .one()
        )
        assert Decimal(str(aggregate["total_theoretical_cost"])) == Decimal("10.000000")
        reservation = (
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.movement_type == "SALE_RESERVATION"
                )
            )
            .mappings()
            .one()
        )
        assert Decimal(str(reservation["quantity_delta"])) == Decimal("-1.000000")
        assert Decimal(str(reservation["unit_cost"])) == Decimal("10.000000")
        assert Decimal(str(reservation["total_cost"])) == Decimal("-10.000000")
        first, second = order["production_tasks"]
        advance_kds_task(session, first["id"], "IN_PROGRESS", BRANCH_A)
        advance_kds_task(session, first["id"], "COMPLETED", BRANCH_A)
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(models.inventory_movements)
                .where(models.inventory_movements.c.movement_type == "SALE_CONSUMPTION")
            ).scalar_one()
            == 0
        )
        advance_kds_task(session, second["id"], "IN_PROGRESS", BRANCH_A)
        advance_kds_task(session, second["id"], "COMPLETED", BRANCH_A)
        assert (
            session.execute(
                sa.select(models.orders.c.status).where(models.orders.c.id == order["id"])
            ).scalar_one()
            == "READY"
        )
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(models.inventory_movements)
                .where(models.inventory_movements.c.movement_type == "SALE_CONSUMPTION")
            ).scalar_one()
            == 1
        )
        # Later catalog changes never reinterpret the already accepted line.
        replacement = save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=1,
            idempotency_key="combo-order-version-002",
            components=[{"product_id": BURGER, "quantity": "2"}],
        )
        assert replacement["version"] == 2
        assert {
            row["composition_version"]
            for row in session.execute(
                sa.select(models.order_line_component_snapshots).where(
                    models.order_line_component_snapshots.c.order_line_id == line_id
                )
            ).mappings()
        } == {1}
        # A later recipe edit cannot reinterpret the frozen component snapshot.
        session.execute(
            models.recipe_components.update()
            .where(models.recipe_components.c.recipe_id == component_rows[0]["recipe_id"])
            .values(gross_quantity=Decimal("0.750000"), net_quantity=Decimal("0.750000"))
        )
        assert {
            Decimal(str(component["gross_quantity"]))
            for row in session.execute(
                sa.select(models.order_line_component_snapshots).where(
                    models.order_line_component_snapshots.c.order_line_id == line_id
                )
            ).mappings()
            for component in row["recipe_components"]
        } == {Decimal("0.500000")}
        cancelled = cancel_order(session, order["id"], "Combo producido", "waste", ACTOR)
        assert cancelled["cancellation_kind"] == "waste"
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(models.inventory_movements)
                .where(models.inventory_movements.c.movement_type == "WASTE")
            ).scalar_one()
            == 1
        )
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    (
        ("archived", "combo_component_out_of_scope"),
        ("unavailable", "combo_component_unavailable"),
        ("required_modifier", "combo_component_selection_required"),
        ("became_combo", "combo_component_nested"),
    ),
)
def test_acceptance_fails_closed_when_a_frozen_component_is_not_operable(
    failure: str, expected_code: str
) -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=0,
            idempotency_key=f"combo-operable-{failure}",
            components=[{"product_id": BURGER, "quantity": "1"}],
        )
        if failure == "archived":
            session.execute(
                models.products.update()
                .where(models.products.c.id == BURGER)
                .values(status="archived")
            )
        elif failure == "unavailable":
            session.execute(
                models.branch_product_availability.insert().values(
                    branch_id=BRANCH_A, product_id=BURGER, is_available=False, updated_at=NOW
                )
            )
        elif failure == "required_modifier":
            session.execute(
                models.modifier_groups.insert().values(
                    id="combo-required-group",
                    organization_id=ORG_ID,
                    product_id=BURGER,
                    name="Elección obligatoria",
                    is_required=True,
                    minimum_selections=1,
                    maximum_selections=1,
                    station=None,
                    display_order=1,
                    status="active",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        else:
            session.execute(
                models.price_versions.insert().values(
                    id="018f6f73-2d0a-74f0-8f1c-000000009398",
                    organization_id=ORG_ID,
                    product_id=BURGER,
                    price_cents=9900,
                    currency="MXN",
                    valid_from=NOW,
                    valid_to=None,
                    created_at=NOW,
                )
            )
            session.commit()
            save_composition(
                session,
                ACTOR,
                BURGER,
                BRANCH_A,
                expected_version=0,
                idempotency_key="component-became-combo",
                components=[{"product_id": DRINK, "quantity": "1"}],
            )
        session.commit()
        assert effective_composition(session, COMBO, BRANCH_A) is not None
        with pytest.raises(BusinessError) as error:
            create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key=f"combo-blocked-{failure}",
            )
        assert error.value.code == expected_code
        session.rollback()
        assert (
            session.execute(
                sa.select(sa.func.count()).select_from(models.production_tasks)
            ).scalar_one()
            == 0
        )
    finally:
        session.close()
        engine.dispose()


def test_acceptance_rejects_expanded_component_quantity_outside_numeric_precision() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        save_composition(
            session,
            ACTOR,
            COMBO,
            None,
            expected_version=0,
            idempotency_key="combo-max-component",
            components=[{"product_id": BURGER, "quantity": "999999999999"}],
        )
        with pytest.raises(BusinessError) as error:
            create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 2}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="combo-expanded-overflow",
            )
        assert error.value.code == "combo_component_quantity_overflow"
        session.rollback()
        assert (
            session.execute(
                sa.select(sa.func.count()).select_from(models.order_line_component_snapshots)
            ).scalar_one()
            == 0
        )
    finally:
        session.close()
        engine.dispose()

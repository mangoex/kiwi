"""Focused API checks for add-only ingredient extras and legacy compatibility."""

# ruff: noqa: E501

import json
import logging
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BRANCH_ID,
    INGREDIENT_VARIATION_GROUP,
    BusinessError,
    _apply_order_modifiers,
    list_product_modifiers,
)
from test_platform_api import _admin_headers, _client_with_seeded_database

BURGER_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
BEEF_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
SYRUP_ID = "018f6f73-2d0a-74f0-8f1c-000000000314"
SODA_ID = "018f6f73-2d0a-74f0-8f1c-000000000113"
BUSINESS_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000015"
WAREHOUSE_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"
UTC = timezone.utc


def _assignment_payload() -> dict[str, object]:
    return {
        "product_ids": [BURGER_ID],
        "category_ids": [],
        "allow_add": True,
        "allow_remove": False,
        "add_quantity": "0.050000",
        "remove_quantity": "0",
        "charge_additional": False,
        "add_price_delta_cents": 0,
    }


def test_ingredient_variation_assignment_is_idempotent_and_rejects_empty_targets() -> None:
    client = _client_with_seeded_database()
    created = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    )
    assert created.status_code == 200
    variation = created.json()
    payload = _assignment_payload()
    headers = {**_admin_headers(), "Idempotency-Key": "ingredient-variation-apply-0001"}
    url = f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments"
    first = client.put(url, headers=headers, json=payload)
    assert first.status_code == 200
    replay = client.put(url, headers=headers, json={**payload, "product_ids": [BURGER_ID]})
    assert replay.status_code == 200 and replay.json() == first.json()
    conflict = client.put(url, headers=headers, json={**payload, "add_quantity": "0.100000"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    empty = client.post(
        f"{url}/preview",
        headers=_admin_headers(),
        json={**payload, "product_ids": [], "category_ids": []},
    )
    assert empty.status_code == 409
    assert empty.json()["detail"]["code"] == "variation_assignment_targets_required"


def test_explicit_surcharge_cents_are_preserved_in_runtime_and_order_total() -> None:
    client = _client_with_seeded_database()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    assignment = client.put(
        f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "surcharge-2050-cents"},
        json={
            **_assignment_payload(),
            "charge_additional": True,
            "add_price_delta_cents": 2050,
        },
    ).json()[0]
    modifiers = client.get(
        f"/api/v1/products/{BURGER_ID}/modifiers", headers=_admin_headers()
    ).json()
    option = next(
        option
        for group in modifiers
        for option in group["options"]
        if option["id"] == assignment["add_option_id"]
    )
    assert option["price_delta_cents"] == 2050
    assert client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 10000}
    ).status_code == 200
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": BURGER_ID,
                    "quantity": 1,
                    "modifiers": [{"option_id": assignment["add_option_id"]}],
                }
            ]
        },
    )
    assert order.status_code == 200
    assert order.json()["lines"][0]["modifier_total_cents"] == 2050


def test_assignment_quantities_reject_float_bool_and_nonfinite_values() -> None:
    client = _client_with_seeded_database()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    url = f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments/preview"
    valid = {**_assignment_payload(), "add_quantity": "0.125000"}
    assert client.post(url, headers=_admin_headers(), json=valid).status_code == 200
    legacy_remove = client.post(
        url,
        headers=_admin_headers(),
        json={**valid, "allow_remove": True},
    )
    assert legacy_remove.status_code == 409
    assert legacy_remove.json()["detail"]["code"] == "ingredient_extra_add_only"
    for field, invalid in (
        ("add_quantity", 0.125),
        ("add_quantity", True),
        ("add_quantity", "NaN"),
        ("add_quantity", "Infinity"),
        ("remove_quantity", False),
        ("remove_quantity", "not-a-decimal"),
    ):
        response = client.post(url, headers=_admin_headers(), json={**valid, field: invalid})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "invalid_variation_quantity"
    for non_finite in (float("nan"), float("inf")):
        response = client.post(
            url,
            headers={**_admin_headers(), "content-type": "application/json"},
            content=json.dumps({**valid, "add_quantity": non_finite}),
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "invalid_variation_quantity"


def test_ingredient_group_refuses_manual_collision_and_archives_then_reuses_options() -> None:
    client = _client_with_seeded_database()
    created = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    url = f"/api/v1/catalog/ingredient-variations/{created['id']}/assignments"
    factory = client.app.state.test_session_factory
    with factory() as session:
        session.execute(
            models.modifier_groups.insert().values(
                id="ingredient-group-collision",
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                product_id=BURGER_ID,
                name=INGREDIENT_VARIATION_GROUP,
                is_required=False,
                minimum_selections=0,
                maximum_selections=1,
                station=None,
                display_order=999,
                status="active",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()
    rejected = client.put(
        url,
        headers={**_admin_headers(), "Idempotency-Key": "ingredient-group-collision"},
        json=_assignment_payload(),
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "variation_group_conflict"

    with factory() as session:
        session.execute(
            models.modifier_groups.delete().where(
                models.modifier_groups.c.id == "ingredient-group-collision"
            )
        )
        session.commit()
    first = client.put(
        url,
        headers={**_admin_headers(), "Idempotency-Key": "ingredient-group-create"},
        json=_assignment_payload(),
    )
    assert first.status_code == 200
    first_row = first.json()[0]
    deleted = client.delete(f"{url}/{BURGER_ID}", headers=_admin_headers())
    assert deleted.status_code == 200
    with factory() as session:
        group = session.execute(
            sa.select(models.modifier_groups).where(
                models.modifier_groups.c.id
                == session.execute(
                    sa.select(models.modifier_options.c.group_id).where(
                        models.modifier_options.c.id == first_row["add_option_id"]
                    )
                ).scalar_one()
            )
        ).mappings().one()
        assert group["status"] == "archived"
        assert group["maximum_selections"] == 0
    replay = client.put(
        url,
        headers={**_admin_headers(), "Idempotency-Key": "ingredient-group-reactivate"},
        json=_assignment_payload(),
    )
    assert replay.status_code == 200
    assert replay.json()[0]["add_option_id"] == first_row["add_option_id"]
    with factory() as session:
        modifiers = list_product_modifiers(session, BURGER_ID)
    ingredient_options = [
        option
        for group in modifiers
        for option in group["options"]
        if option.get("variation_kind") == "ingredient_extra"
    ]
    assert {option["action"] for option in ingredient_options} == {"add"}


def test_ingredient_preview_uses_effective_recipe_and_emits_structured_logs(caplog) -> None:
    caplog.set_level(logging.INFO)
    client = _client_with_seeded_database()
    created = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    preview = client.post(
        f"/api/v1/catalog/ingredient-variations/{created['id']}/assignments/preview",
        headers=_admin_headers(),
        json={**_assignment_payload(), "product_ids": ["missing-product"]},
    )
    assert preview.status_code == 200
    assert preview.json()[0]["reason"] == "product_inactive_or_missing"
    assert any("ingredient_variation.preview" in record.message for record in caplog.records)


def test_legacy_remove_ingredient_is_hidden_and_manual_selection_is_rejected() -> None:
    client = _client_with_seeded_database()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    assignment = client.put(
        f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "missing-remove-assignment"},
        json=_assignment_payload(),
    ).json()[0]
    factory = client.app.state.test_session_factory
    with factory() as session:
        remove_id = "legacy-ingredient-remove-option"
        second_remove_id = "legacy-ingredient-remove-option-two"
        second_variation_id = "legacy-ingredient-variation-two"
        group_id = session.execute(sa.select(models.modifier_options.c.group_id).where(models.modifier_options.c.id == assignment["add_option_id"])).scalar_one()
        session.execute(models.modifier_options.insert().values(id=remove_id, group_id=group_id, name="Sin carne molida", effect_type="remove", affected_item_id=BEEF_ID, inventory_effect=True, add_quantity="0", remove_quantity="0", price_delta_cents=0, kitchen_text="Sin carne molida", display_order=2, status="active", created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
        session.execute(models.ingredient_variation_products.update().where(models.ingredient_variation_products.c.id == assignment["id"]).values(remove_option_id=remove_id, allow_remove=True))
        now = datetime.now(UTC)
        session.execute(models.modifier_options.insert().values(id=second_remove_id, group_id=group_id, name="Sin jarabe", effect_type="remove", affected_item_id=SYRUP_ID, inventory_effect=True, add_quantity="0", remove_quantity="0", price_delta_cents=0, kitchen_text="Sin jarabe", display_order=3, status="active", created_at=now, updated_at=now))
        session.execute(models.ingredient_variations.insert().values(id=second_variation_id, organization_id="018f6f73-2d0a-74f0-8f1c-000000000001", inventory_item_id=SYRUP_ID, add_label="Porción extra de jarabe", remove_label="Sin jarabe", status="active", created_at=now, updated_at=now))
        session.execute(models.ingredient_variation_products.insert().values(id="legacy-ingredient-assignment-two", variation_id=second_variation_id, product_id=BURGER_ID, allow_add=False, allow_remove=True, add_quantity="0", remove_quantity="0", charge_additional=False, add_price_delta_cents=0, add_option_id=None, remove_option_id=second_remove_id, status="active", created_at=now, updated_at=now))
        session.commit()
        options = [
            option
            for group in list_product_modifiers(session, BURGER_ID, BRANCH_ID)
            for option in group["options"]
        ]
        assert remove_id not in {option["id"] for option in options}
        with pytest.raises(BusinessError) as error:
            _apply_order_modifiers(
                session,
                BURGER_ID,
                BRANCH_ID,
                1,
                [],
                [{"option_id": remove_id}],
            )
        assert error.value.code == "ingredient_extra_add_only"
        # More than one legacy removal must take the same business-error path,
        # without attempting to resolve groups, snapshots or inventory effects.
        with pytest.raises(BusinessError) as multiple_error:
            _apply_order_modifiers(
                session,
                BURGER_ID,
                BRANCH_ID,
                1,
                [],
                [{"option_id": remove_id}, {"option_id": second_remove_id}],
            )
        assert multiple_error.value.code == "ingredient_extra_add_only"


def test_definition_defaults_labels_lifecycle_events_and_assignment_detail() -> None:
    client = _client_with_seeded_database()
    created = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    )
    assert created.status_code == 200
    variation = created.json()
    assert variation["add_label"] == "Con carne molida"
    assert variation["remove_label"] == "Sin carne molida"
    listed = client.get("/api/v1/catalog/ingredient-variations", headers=_admin_headers()).json()
    assert next(row for row in listed if row["id"] == variation["id"])["unit_code"] == "g"
    duplicate = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "ingredient_variation_exists"
    null_label = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": SYRUP_ID, "add_label": None},
    )
    assert null_label.status_code == 409
    assert null_label.json()["detail"]["code"] == "invalid_ingredient_variation_label"
    url = f"/api/v1/catalog/ingredient-variations/{variation['id']}"
    assigned = client.put(
        f"{url}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "definition-lifecycle-assign"},
        json=_assignment_payload(),
    ).json()[0]
    updated = client.put(url, headers=_admin_headers(), json={"add_label": "Con proteína"})
    assert updated.status_code == 200
    factory = client.app.state.test_session_factory
    with factory() as session:
        option = session.execute(
            sa.select(models.modifier_options).where(
                models.modifier_options.c.id == assigned["add_option_id"]
            )
        ).mappings().one()
        assert option["name"] == option["kitchen_text"] == "Con proteína"
    detail = client.get(url, headers=_admin_headers()).json()
    assert detail["assignments"][0]["product_sku"] == "KIWI-BURGER"
    assert detail["assignments"][0]["category_name"] == "Comida"
    assert client.put(url, headers=_admin_headers(), json={"status": "archived"}).status_code == 200
    assert client.put(url, headers=_admin_headers(), json={"status": "active"}).status_code == 200
    with factory() as session:
        actions = set(
            session.execute(
                sa.select(models.audit_events.c.action).where(
                    models.audit_events.c.entity_id == variation["id"]
                )
            ).scalars()
        )
    assert {
        "ingredient_variation.created",
        "ingredient_variation.updated",
        "ingredient_variation.archived",
        "ingredient_variation.reactivated",
        "ingredient_variation.assignment.bulk_applied",
    } <= actions


def test_individual_update_rejects_remove_actions_and_emits_no_legacy_option() -> None:
    client = _client_with_seeded_database()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    url = f"/api/v1/catalog/ingredient-variations/{variation['id']}"
    assignment = client.put(
        f"{url}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "reactivation-create"},
        json=_assignment_payload(),
    ).json()[0]
    updated = client.put(
        f"{url}/assignments/{BURGER_ID}",
        headers={**_admin_headers(), "Idempotency-Key": "reactivation-update"},
        json={**_assignment_payload(), "allow_add": False, "allow_remove": True},
    )
    assert updated.status_code == 409
    assert updated.json()["detail"]["code"] == "ingredient_extra_add_only"
    assert client.put(url, headers=_admin_headers(), json={"status": "archived"}).status_code == 200
    assert client.put(url, headers=_admin_headers(), json={"status": "active"}).status_code == 200
    modifiers = client.get(
        f"/api/v1/products/{BURGER_ID}/modifiers", headers=_admin_headers()
    ).json()
    option_ids = {option["id"] for group in modifiers for option in group["options"]}
    assert assignment["add_option_id"] in option_ids
    factory = client.app.state.test_session_factory
    with factory() as session:
        updates = session.execute(
            sa.select(sa.func.count()).select_from(models.audit_events).where(
                models.audit_events.c.action == "ingredient_variation.assignment.updated"
            )
        ).scalar_one()
    assert updates == 0


def test_preview_category_deduplicates_and_applies_active_products_only() -> None:
    client = _client_with_seeded_database()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    url = f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments"
    payload = {
        **_assignment_payload(),
        "product_ids": [BURGER_ID, BURGER_ID, "018f6f73-2d0a-74f0-8f1c-000000000112"],
        "category_ids": ["018f6f73-2d0a-74f0-8f1c-000000000101"],
    }
    preview = client.post(f"{url}/preview", headers=_admin_headers(), json=payload)
    assert preview.status_code == 200
    rows = preview.json()
    assert {row["sku"] for row in rows} == {"KIWI-BURGER", "KIWI-FRIES"}
    assert all(row["category"] == "Comida" for row in rows)
    assert all(row["compatible"] for row in rows)
    applied = client.put(
        url,
        headers={**_admin_headers(), "Idempotency-Key": "mixed-remove-is-atomic"},
        json=payload,
    )
    assert applied.status_code == 200
    assert len(applied.json()) == 2
    foreign_category = client.post(
        f"{url}/preview",
        headers=_admin_headers(),
        json={**payload, "product_ids": [BURGER_ID], "category_ids": ["missing-category"]},
    )
    assert foreign_category.status_code == 409
    assert foreign_category.json()["detail"]["code"] == "invalid_variation_assignment_targets"


def test_ingredient_additions_free_and_priced_preserve_snapshot_cost_and_kitchen_history() -> None:
    client = _client_with_seeded_database()
    factory = client.app.state.test_session_factory
    with factory() as session:
        session.execute(
            models.inventory_cost_states.delete().where(
                models.inventory_cost_states.c.branch_id == BRANCH_ID,
                models.inventory_cost_states.c.warehouse_id == WAREHOUSE_ID,
                models.inventory_cost_states.c.item_id.in_([BEEF_ID, SYRUP_ID]),
            )
        )
        now = datetime.now(UTC)
        session.execute(
            models.inventory_cost_states.insert(),
            [
                {"branch_id": BRANCH_ID, "warehouse_id": WAREHOUSE_ID, "item_id": BEEF_ID, "quantity_on_hand": 1000, "average_unit_cost": "2.5", "last_unit_cost": "2.5", "last_supplier_id": None, "last_cost_at": now, "updated_at": now},
                {"branch_id": BRANCH_ID, "warehouse_id": WAREHOUSE_ID, "item_id": SYRUP_ID, "quantity_on_hand": 1000, "average_unit_cost": "3", "last_unit_cost": "3", "last_supplier_id": None, "last_cost_at": now, "updated_at": now},
            ],
        )
        session.commit()
    beef = client.post("/api/v1/catalog/ingredient-variations", headers=_admin_headers(), json={"inventory_item_id": BEEF_ID}).json()
    beef_assignment = client.put(
        f"/api/v1/catalog/ingredient-variations/{beef['id']}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "priced-beef"},
        json={**_assignment_payload(), "add_quantity": "10.125", "charge_additional": True, "add_price_delta_cents": 1250},
    ).json()[0]
    syrup = client.post("/api/v1/catalog/ingredient-variations", headers=_admin_headers(), json={"inventory_item_id": SYRUP_ID}).json()
    syrup_assignment = client.put(
        f"/api/v1/catalog/ingredient-variations/{syrup['id']}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "free-syrup"},
        json={**_assignment_payload(), "product_ids": [SODA_ID], "add_quantity": "5.500", "charge_additional": False, "add_price_delta_cents": 0},
    ).json()[0]
    assert client.post("/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 10000}).status_code == 200
    burger_order = client.post("/api/v1/orders", headers=_admin_headers(), json={"lines": [{"product_id": BURGER_ID, "quantity": 2, "modifiers": [{"option_id": beef_assignment["add_option_id"]}]}]})
    assert burger_order.status_code == 200
    burger = burger_order.json()
    assert burger["lines"][0]["modifier_total_cents"] == 2500
    beef_component = next(component for component in burger["consumption_snapshots"][0]["components"] if component["item_id"] == BEEF_ID)
    assert float(beef_component["gross_quantity"]) == 260.25
    assert float(beef_component["unit_cost"]) == 2.5
    reservations = client.get(
        f"/api/v1/inventory/kardex?item_id={BEEF_ID}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_RESERVATION" and float(row["quantity_delta"]) == -260.25
        for row in reservations
    )
    soda_order = client.post("/api/v1/orders", headers=_admin_headers(), json={"lines": [{"product_id": SODA_ID, "quantity": 1, "modifiers": [{"option_id": syrup_assignment["add_option_id"]}]}]})
    assert soda_order.status_code == 200
    soda = soda_order.json()
    assert soda["lines"][0]["modifier_total_cents"] == 0
    syrup_component = next(component for component in soda["consumption_snapshots"][0]["components"] if component["item_id"] == SYRUP_ID)
    assert float(syrup_component["gross_quantity"]) == 85.5
    assert float(syrup_component["unit_cost"]) == 3
    task_id = burger["production_tasks"][0]["id"]
    assert client.post(f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "IN_PROGRESS"}).status_code == 200
    assert client.post(f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "COMPLETED"}).status_code == 200
    consumptions = client.get(
        f"/api/v1/inventory/kardex?item_id={BEEF_ID}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_CONSUMPTION" and float(row["quantity_delta"]) == -260.25
        for row in consumptions
    )
    assert client.post(
        f"/api/v1/orders/{burger['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": burger["total_cents"], "method": "cash"},
    ).status_code == 200
    assert client.delete(f"/api/v1/catalog/ingredient-variations/{beef['id']}/assignments/{BURGER_ID}", headers=_admin_headers()).status_code == 200
    kitchen = next(job for job in client.get("/api/v1/print-jobs").json() if job["order_id"] == burger["id"] and job["job_type"] == "kitchen")
    assert any(modifier["kitchen_text"] == beef["add_label"] for modifier in kitchen["payload"]["lines"][0]["selected_modifiers"])
    with factory() as session:
        actions = set(
            session.execute(
                sa.select(models.audit_events.c.action).where(
                    models.audit_events.c.action == "ingredient_variation.assignment.archived"
                )
            ).scalars()
        )
    assert "ingredient_variation.assignment.archived" in actions


def test_apply_revalidates_recipe_after_preview_without_partial_command_or_audit() -> None:
    client = _client_with_seeded_database()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    url = f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments"
    payload = _assignment_payload()
    preview = client.post(f"{url}/preview", headers=_admin_headers(), json=payload)
    assert preview.status_code == 200 and preview.json()[0]["compatible"] is True
    factory = client.app.state.test_session_factory
    with factory() as session:
        recipe_ids = session.execute(
            sa.select(models.recipes.c.id).where(
                models.recipes.c.product_id == BURGER_ID,
                models.recipes.c.status == "active",
            )
        ).scalars().all()
        session.execute(models.recipe_components.delete().where(models.recipe_components.c.recipe_id.in_(recipe_ids)))
        session.commit()
    applied = client.put(
        url,
        headers={**_admin_headers(), "Idempotency-Key": "preview-then-recipe-change"},
        json=payload,
    )
    assert applied.status_code == 409
    assert applied.json()["detail"]["code"] == "variation_assignment_incompatible"
    with factory() as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.ingredient_variation_products).where(
                models.ingredient_variation_products.c.variation_id == variation["id"]
            )
        ).scalar_one() == 0
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.ingredient_variation_commands).where(
                models.ingredient_variation_commands.c.idempotency_key == "preview-then-recipe-change"
            )
        ).scalar_one() == 0
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.audit_events).where(
                models.audit_events.c.action == "ingredient_variation.assignment.bulk_applied",
                models.audit_events.c.entity_id == variation["id"],
            )
        ).scalar_one() == 0


def test_branch_ingredient_overrides_are_scoped_to_supervisor_branch_and_cashier_is_denied(
) -> None:
    client = _client_with_seeded_database()
    branch = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Norte", "code": "NORTE", "business_unit_id": BUSINESS_UNIT_ID},
    ).json()
    supervisor_role = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Supervisor de sucursal", "scope": "branch"},
    ).json()
    cashier_role = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Cajero", "scope": "branch"},
    ).json()
    supervisor = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "supervisor.norte@kiwi.test",
            "display_name": "Supervisor Norte",
            "password": "Temporal123+",
            "role_id": supervisor_role["id"],
            "branch_id": branch["id"],
        },
    ).json()
    cashier = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "cajero.norte@kiwi.test",
            "display_name": "Cajero Norte",
            "password": "Temporal123+",
            "role_id": cashier_role["id"],
            "branch_id": branch["id"],
        },
    ).json()
    variation = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    ).json()
    assignments = client.put(
        f"/api/v1/catalog/ingredient-variations/{variation['id']}/assignments",
        headers={**_admin_headers(), "Idempotency-Key": "branch-ingredient-assignment"},
        json=_assignment_payload(),
    ).json()
    option_id = assignments[0]["add_option_id"]
    supervisor_headers = {"X-Actor-User-Id": supervisor["id"]}
    own_rows = client.get(
        "/api/v1/branch-administration/catalog/ingredient-variations",
        headers=supervisor_headers,
    )
    assert own_rows.status_code == 200
    assert own_rows.json()[0]["inventory_item_name"] == "Carne molida"
    assert own_rows.json()[0]["unit_code"] == "g"
    configured = client.put(
        f"/api/v1/branch-administration/catalog/ingredient-variations/{option_id}",
        headers=supervisor_headers,
        json={"action": "unavailable"},
    )
    assert configured.status_code == 200
    assert configured.json()["branch_id"] == branch["id"]
    other_branch_rows = client.get(
        "/api/v1/branch-administration/catalog/ingredient-variations",
        headers=_admin_headers(),
        params={"branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003"},
    ).json()
    other_option = next(row for row in other_branch_rows if row["option_id"] == option_id)
    assert other_option["override"] is None
    forbidden_branch = client.get(
        "/api/v1/branch-administration/catalog/ingredient-variations",
        headers=supervisor_headers,
        params={"branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003"},
    )
    assert forbidden_branch.status_code == 403
    cashier_rows = client.get(
        "/api/v1/branch-administration/catalog/ingredient-variations",
        headers={"X-Actor-User-Id": cashier["id"]},
    )
    assert cashier_rows.status_code == 403


def test_corporate_ingredient_variation_detail_update_and_archive_are_organization_scoped() -> None:
    client = _client_with_seeded_database()
    foreign_variation_id = "ingredient-variation-foreign-0001"
    now = datetime.now(UTC)
    factory = client.app.state.test_session_factory
    with factory() as session:
        session.execute(
            models.ingredient_variations.insert().values(
                id=foreign_variation_id,
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000099",
                inventory_item_id=BEEF_ID,
                add_label="Con ajeno",
                remove_label="Sin ajeno",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    detail_url = f"/api/v1/catalog/ingredient-variations/{foreign_variation_id}"
    assert client.get(detail_url, headers=_admin_headers()).status_code == 404
    assert client.put(
        detail_url, headers=_admin_headers(), json={"add_label": "Con acceso indebido"}
    ).status_code == 404
    assert client.delete(
        f"{detail_url}/assignments/{BURGER_ID}", headers=_admin_headers()
    ).status_code == 404

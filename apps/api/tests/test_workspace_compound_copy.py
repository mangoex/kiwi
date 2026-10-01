"""SR-WORKSPACE-001 full selectable copy and pure selection regressions."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from restaurant_os import models
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)

SOURCE = "018f6f73-2d0a-74f0-8f1c-000000000111"
COMPONENT = "018f6f73-2d0a-74f0-8f1c-000000000112"
TARGET = "018f6f73-2d0a-74f0-8f1c-000000000811"
BRANCH = BRANCH_ID


def _setup():
    client = _client_with_seeded_database()
    factory = _test_session_factory(client)
    with factory() as session:
        source = dict(
            session.execute(sa.select(models.products).where(models.products.c.id == SOURCE))
            .mappings()
            .one()
        )
        session.execute(
            models.products.insert().values(
                **{**source, "id": TARGET, "sku": "SR-TARGET", "name": "Destino independiente"}
            )
        )
        session.commit()
    groups = [
        {
            "name": "Acompañamientos",
            "is_required": True,
            "minimum_selections": 1,
            "maximum_selections": 2,
            "included_selections": 1,
            "options": [
                {
                    "name": "Papas",
                    "effect_type": "product_component",
                    "component_product_id": COMPONENT,
                    "component_quantity": "1",
                    "price_delta_cents": 1000,
                },
                {"name": "Salsa", "effect_type": "instruction", "price_delta_cents": 500},
            ],
        }
    ]
    response = client.put(
        f"/api/v1/products/{SOURCE}/modifier-configuration",
        headers={**_admin_headers(), "Idempotency-Key": "sr-copy-source-seed"},
        json={"expected_version": 0, "groups": groups},
    )
    assert response.status_code == 200, response.text
    return client, factory, response.json()


def _effects(factory):
    with factory() as session:
        return {
            table.name: list(session.execute(sa.select(table)).mappings())
            for table in (
                models.products,
                models.recipes,
                models.price_versions,
                models.modifier_groups,
                models.modifier_options,
                models.product_modifier_configurations,
                models.modifier_configuration_commands,
                models.inventory_movements,
                models.order_lines,
                models.order_line_consumption_snapshots,
                models.audit_events,
            )
        }


def test_full_copy_owns_ids_replays_and_preserves_non_modifier_dependencies():
    client, factory, source = _setup()
    before = _effects(factory)
    payload = {
        "source_product_id": SOURCE,
        "expected_source_version": 1,
        "expected_target_version": 0,
    }
    headers = {**_admin_headers(), "Idempotency-Key": "sr-full-copy-command-001"}
    response = client.post(
        f"/api/v1/products/{TARGET}/modifier-configuration/copy", headers=headers, json=payload
    )
    assert response.status_code == 200, response.text
    copied = response.json()
    assert copied["version"] == 1
    assert copied["groups"][0]["id"] != source["groups"][0]["id"]
    assert [row["id"] for row in copied["groups"][0]["options"]] != [
        row["id"] for row in source["groups"][0]["options"]
    ]
    for field in (
        "minimum_selections",
        "maximum_selections",
        "included_selections",
        "display_order",
    ):
        assert copied["groups"][0][field] == source["groups"][0][field]
    after = _effects(factory)
    for table in (
        "products",
        "recipes",
        "price_versions",
        "inventory_movements",
        "order_lines",
        "order_line_consumption_snapshots",
    ):
        assert after[table] == before[table]
    replay = client.post(
        f"/api/v1/products/{TARGET}/modifier-configuration/copy", headers=headers, json=payload
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["result"] == "replay"
    assert _effects(factory) == after
    conflict = client.post(
        f"/api/v1/products/{TARGET}/modifier-configuration/copy",
        headers=headers,
        json={**payload, "expected_source_version": 0},
    )
    assert conflict.status_code == 409
    assert _effects(factory) == after


def test_copy_rejects_stale_source_and_self_component_without_partial_changes():
    client, factory, _ = _setup()
    before = _effects(factory)
    for target, source_version in ((TARGET, 0), (COMPONENT, 1)):
        response = client.post(
            f"/api/v1/products/{target}/modifier-configuration/copy",
            headers={**_admin_headers(), "Idempotency-Key": "sr-copy-reject-" + target},
            json={
                "source_product_id": SOURCE,
                "expected_source_version": source_version,
                "expected_target_version": 0,
            },
        )
        assert response.status_code == 409, response.text
    assert _effects(factory) == before


def test_selection_preview_uses_included_price_and_creates_no_order_or_reservation():
    client, factory, source = _setup()
    before = _effects(factory)
    options = source["groups"][0]["options"]
    response = client.post(
        f"/api/v1/products/{SOURCE}/modifier-configuration/selection-preview",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH,
            "quantity": 1,
            "modifiers": [{"option_id": option["id"]} for option in options],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["modifier_total_cents"] == 500
    assert response.json()["consumption"]["components"]
    assert _effects(factory) == before


def test_selection_requires_effective_recipe_in_current_branch():
    client, factory, source = _setup()
    other_branch = "018f6f73-2d0a-74f0-8f1c-000000008803"
    with factory() as session:
        branch = dict(
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH))
            .mappings()
            .one()
        )
        session.execute(
            models.branches.insert().values(**{**branch, "id": other_branch, "code": "SR-SECOND"})
        )
        session.execute(
            models.recipes.update()
            .where(models.recipes.c.product_id == COMPONENT, models.recipes.c.status == "active")
            .values(branch_id=other_branch)
        )
        session.commit()
    before = _effects(factory)
    option = source["groups"][0]["options"][0]
    response = client.post(
        f"/api/v1/products/{SOURCE}/modifier-configuration/selection-preview",
        headers=_admin_headers(),
        json={"branch_id": BRANCH, "quantity": 1, "modifiers": [{"option_id": option["id"]}]},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "modifier_option_unavailable"
    assert _effects(factory) == before


def test_copy_rollback_preserves_destination_when_final_audit_fails(monkeypatch):
    from restaurant_os import modifier_configuration as configuration

    client, factory, _ = _setup()
    before = _effects(factory)
    original = configuration._audit

    def fail_copy_audit(*args, **kwargs):
        if (
            "modifier_configuration.copied" in args
            or kwargs.get("action") == "modifier_configuration.copied"
        ):
            raise RuntimeError("synthetic copy audit failure")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(configuration, "_audit", fail_copy_audit)
        with pytest.raises(RuntimeError, match="synthetic copy audit failure"):
            client.post(
                f"/api/v1/products/{TARGET}/modifier-configuration/copy",
                headers={**_admin_headers(), "Idempotency-Key": "sr-copy-audit-rollback"},
                json={
                    "source_product_id": SOURCE,
                    "expected_source_version": 1,
                    "expected_target_version": 0,
                },
            )
    assert _effects(factory) == before

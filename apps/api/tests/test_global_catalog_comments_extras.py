from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.models import (
    audit_events,
    modifier_groups,
    modifier_options,
    order_comment_presets,
    order_comment_products,
    permissions,
    role_permissions,
    roles,
    user_roles,
    users,
)
from restaurant_os.operations import BusinessError, _variation_quantity, parse_order_comment_values
from test_platform_api import (
    ADMIN_ROLE_ID,
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
    _test_session_factory,
)

BURGER_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
FRIES_ID = "018f6f73-2d0a-74f0-8f1c-000000000112"
SODA_ID = "018f6f73-2d0a-74f0-8f1c-000000000113"
BEEF_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"


def test_global_comment_parser_deduplicates_without_erasing_visible_text() -> None:
    assert parse_order_comment_values(
        " Sin azúcar,\nSIN AZUCAR  Sin cebolla, Muy caliente  Para llevar "
    ) == [
        "Sin azúcar",
        "Sin cebolla",
        "Muy caliente",
        "Para llevar",
    ]
    assert _variation_quantity("0.125000") == Decimal("0.125000")
    with pytest.raises(BusinessError, match="six decimal places"):
        _variation_quantity("0.0000005")


def test_global_comments_preview_bulk_relationships_and_product_filter() -> None:
    client = _client_with_seeded_database()
    preview = client.post(
        "/api/v1/catalog/order-comments/bulk/preview",
        headers=_admin_headers(),
        json={
            "comments": "Sin azúcar,\nSIN AZUCAR, Sin cebolla",
            "product_ids": [BURGER_ID, FRIES_ID],
        },
    )
    assert preview.status_code == 200
    assert len(preview.json()["created"]) == 2
    assert preview.json()["duplicates"] == ["SIN AZUCAR"]

    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={
            "comments": "Sin azúcar,\nSIN AZUCAR, Sin cebolla",
            "product_ids": [BURGER_ID, FRIES_ID],
        },
    )
    assert applied.status_code == 200
    assert applied.json()["relation_count"] == 4

    second = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "SIN AZUCAR", "product_ids": [BURGER_ID]},
    )
    assert second.status_code == 200
    assert second.json()["existing"]

    burger_names = {
        option["name"]
        for group in client.get(
            f"/api/v1/products/{BURGER_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    fries_names = {
        option["name"]
        for group in client.get(
            f"/api/v1/products/{FRIES_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    assert burger_names == {"Sin azúcar", "Sin cebolla"}
    assert fries_names == burger_names

    forbidden = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sucursal", "product_ids": [BURGER_ID], "branch_id": BRANCH_ID},
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "global_catalog_branch_override"


def test_global_comment_payload_lists_products_and_product_ids_consistently() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin hielo", "product_ids": [BURGER_ID, FRIES_ID]},
    )
    assert applied.status_code == 200
    comment_id = applied.json()["items"][0]["id"]

    listed = client.get("/api/v1/catalog/order-comments", headers=_admin_headers())
    assert listed.status_code == 200
    before = next(item for item in listed.json() if item["id"] == comment_id)
    assert {product["product_id"] for product in before["products"]} == {
        BURGER_ID,
        FRIES_ID,
    }
    assert set(before["product_ids"]) == {BURGER_ID, FRIES_ID}
    assert all(product["product_name"] and product["product_sku"] for product in before["products"])


def test_global_comment_products_can_be_replaced_exactly_with_audit() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin hielo", "product_ids": [BURGER_ID, FRIES_ID]},
    )
    assert applied.status_code == 200
    comment_id = applied.json()["items"][0]["id"]

    replaced = client.put(
        f"/api/v1/catalog/order-comments/{comment_id}/products",
        headers=_admin_headers(),
        json={"product_ids": [FRIES_ID, SODA_ID]},
    )
    assert replaced.status_code == 200
    assert {product["product_id"] for product in replaced.json()["products"]} == {
        FRIES_ID,
        SODA_ID,
    }

    refreshed = client.get("/api/v1/catalog/order-comments", headers=_admin_headers()).json()
    stored = next(item for item in refreshed if item["id"] == comment_id)
    assert {product["product_id"] for product in stored["products"]} == {FRIES_ID, SODA_ID}

    burger_comments = {
        option["name"]
        for group in client.get(
            f"/api/v1/products/{BURGER_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    soda_comments = {
        option["name"]
        for group in client.get(
            f"/api/v1/products/{SODA_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    assert "Sin hielo" not in burger_comments
    assert "Sin hielo" in soda_comments

    rejected = client.put(
        f"/api/v1/catalog/order-comments/{comment_id}/products",
        headers=_admin_headers(),
        json={"product_ids": []},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "order_comment_products_required"
    after_rejection = client.get(
        "/api/v1/catalog/order-comments", headers=_admin_headers()
    ).json()
    after_products = next(item for item in after_rejection if item["id"] == comment_id)["products"]
    assert {product["product_id"] for product in after_products} == {
        FRIES_ID,
        SODA_ID,
    }

    session_factory = _test_session_factory(client)
    with session_factory() as session:
        event = session.execute(
            audit_events.select().where(
                audit_events.c.action == "order_comment.products_replaced",
                audit_events.c.entity_id == comment_id,
            )
        ).mappings().one()
        assert event["actor_user_id"] is not None
        assert event["payload"] == {"products": 2, "archived_relations": 1}


def test_all_active_global_comments_can_be_archived_atomically_with_audit() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin hielo, Sin cebolla", "product_ids": [BURGER_ID]},
    )
    assert applied.status_code == 200
    comment_ids = {item["id"] for item in applied.json()["items"]}

    session_factory = _test_session_factory(client)
    catalog_permission_id = "018f6f73-2d0a-74f0-8f1c-000000000902"
    with session_factory() as session:
        session.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == ADMIN_ROLE_ID,
                role_permissions.c.permission_id == catalog_permission_id,
            )
        )
        session.commit()
    denied = client.post(
        "/api/v1/catalog/order-comments/archive-all",
        headers=_admin_headers(),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "permission_denied"
    with session_factory() as session:
        session.execute(
            role_permissions.insert().values(
                role_id=ADMIN_ROLE_ID,
                permission_id=catalog_permission_id,
            )
        )
        session.commit()

    archived = client.post(
        "/api/v1/catalog/order-comments/archive-all",
        headers=_admin_headers(),
    )
    assert archived.status_code == 200
    assert archived.json() == {"archived_count": 2}

    listed = client.get("/api/v1/catalog/order-comments", headers=_admin_headers()).json()
    assert {item["id"] for item in listed if item["status"] == "archived"} == comment_ids
    published = {
        option["id"]
        for group in client.get(
            f"/api/v1/products/{BURGER_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    assert published.isdisjoint(comment_ids)
    assert client.post(
        "/api/v1/catalog/order-comments/archive-all",
        headers=_admin_headers(),
    ).json() == {"archived_count": 0}

    with session_factory() as session:
        preserved_relations = session.execute(
            order_comment_products.select().where(
                order_comment_products.c.comment_preset_id.in_(comment_ids),
            )
        ).mappings().all()
        assert len(preserved_relations) == 2
        assert all(relation["status"] == "active" for relation in preserved_relations)
        events = session.execute(
            audit_events.select().where(
                audit_events.c.action == "order_comment.all_archived",
            )
        ).mappings().all()
        assert len(events) == 2
        assert [event["payload"]["archived_count"] for event in events] == [2, 0]
        assert all(event["actor_user_id"] is not None for event in events)


def test_current_and_legacy_comments_can_be_deleted_with_recovery_audit() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin hielo, Sin cebolla", "product_ids": [BURGER_ID]},
    )
    assert applied.status_code == 200
    comment_ids = [item["id"] for item in applied.json()["items"]]

    legacy = client.post(
        f"/api/v1/products/{BURGER_ID}/variation-notes",
        headers=_admin_headers(),
        json={"name": "Comentario heredado"},
    )
    assert legacy.status_code == 200

    deleted_one = client.delete(
        f"/api/v1/catalog/order-comments/{comment_ids[0]}",
        headers=_admin_headers(),
    )
    assert deleted_one.status_code == 200
    assert deleted_one.json() == {
        "deleted_count": 1,
        "deleted_relation_count": 1,
        "deleted_legacy_count": 0,
        "deleted_legacy_group_count": 0,
    }

    session_factory = _test_session_factory(client)
    catalog_permission_id = "018f6f73-2d0a-74f0-8f1c-000000000902"
    with session_factory() as session:
        session.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == ADMIN_ROLE_ID,
                role_permissions.c.permission_id == catalog_permission_id,
            )
        )
        session.commit()
    denied = client.delete(
        "/api/v1/catalog/order-comments/all",
        headers=_admin_headers(),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "permission_denied"
    with session_factory() as session:
        session.execute(
            role_permissions.insert().values(
                role_id=ADMIN_ROLE_ID,
                permission_id=catalog_permission_id,
            )
        )
        session.commit()

    deleted_rest = client.delete(
        "/api/v1/catalog/order-comments/all",
        headers=_admin_headers(),
    )
    assert deleted_rest.status_code == 200
    assert deleted_rest.json() == {
        "deleted_count": 1,
        "deleted_relation_count": 1,
        "deleted_legacy_count": 1,
        "deleted_legacy_group_count": 1,
    }
    assert client.delete(
        "/api/v1/catalog/order-comments/all",
        headers=_admin_headers(),
    ).json() == {
        "deleted_count": 0,
        "deleted_relation_count": 0,
        "deleted_legacy_count": 0,
        "deleted_legacy_group_count": 0,
    }

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(order_comment_presets)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(order_comment_products)) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(modifier_options).where(
                modifier_options.c.id == legacy.json()["id"]
            )
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(modifier_groups).where(
                sa.func.lower(sa.func.trim(modifier_groups.c.name)).in_(
                    ("variaciones y cambios", "comentarios del pedido")
                )
            )
        ) == 0
        deleted_events = session.execute(
            audit_events.select()
            .where(audit_events.c.action == "order_comment.deleted")
            .order_by(audit_events.c.created_at)
        ).mappings().all()
        assert len(deleted_events) == 2
        assert {event["entity_id"] for event in deleted_events} == set(comment_ids)
        assert all(event["payload"]["preset"]["status"] == "active" for event in deleted_events)
        assert all(event["payload"]["product_ids"] == [BURGER_ID] for event in deleted_events)
        assert all(len(event["payload"]["relations"]) == 1 for event in deleted_events)
        batch_events = session.execute(
            audit_events.select()
            .where(audit_events.c.action == "order_comment.all_deleted")
            .order_by(audit_events.c.created_at)
        ).mappings().all()
        assert [event["payload"]["deleted_count"] for event in batch_events] == [1, 0]
        legacy_events = session.execute(
            audit_events.select().where(
                audit_events.c.action == "variation_note.legacy_deleted"
            )
        ).mappings().all()
        assert len(legacy_events) == 1
        assert legacy_events[0]["entity_id"] == legacy.json()["id"]
        assert legacy_events[0]["payload"]["option"]["name"] == "Comentario heredado"
        assert legacy_events[0]["payload"]["group"]["product_id"] == BURGER_ID
        group_events = session.execute(
            audit_events.select().where(
                audit_events.c.action == "variation_note.legacy_group_deleted"
            )
        ).mappings().all()
        assert len(group_events) == 1
        assert group_events[0]["payload"]["deleted_option_ids"] == [legacy.json()["id"]]


def test_branch_scoped_catalog_manager_cannot_mutate_corporate_comments() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin hielo", "product_ids": [BURGER_ID]},
    )
    assert applied.status_code == 200
    comment_id = applied.json()["items"][0]["id"]
    branch_role_id = "018f6f73-2d0a-74f0-8f1c-000000009731"
    branch_user_id = "018f6f73-2d0a-74f0-8f1c-000000009732"
    now = datetime(2026, 10, 24, tzinfo=UTC)
    with _test_session_factory(client)() as session:
        permission_id = session.scalar(
            sa.select(permissions.c.id).where(permissions.c.code == "catalog.manage")
        )
        assert permission_id is not None
        session.execute(
            roles.insert().values(
                id=branch_role_id,
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                name="Gestor de catálogo local",
                scope="branch",
                created_at=now,
            )
        )
        session.execute(
            users.insert().values(
                id=branch_user_id,
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                email="branch-catalog@example.test",
                display_name="Gestor local",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            role_permissions.insert().values(
                role_id=branch_role_id,
                permission_id=permission_id,
            )
        )
        session.execute(
            user_roles.insert().values(
                user_id=branch_user_id,
                role_id=branch_role_id,
                branch_id=BRANCH_ID,
            )
        )
        session.commit()
    token = create_session_token({"sub": branch_user_id}, get_settings().secret_key)
    branch_headers = {"Authorization": f"Bearer {token}"}

    for method, path in (
        (client.post, "/api/v1/catalog/order-comments/archive-all"),
        (client.delete, "/api/v1/catalog/order-comments/all"),
        (client.delete, f"/api/v1/catalog/order-comments/{comment_id}"),
    ):
        response = method(path, headers=branch_headers)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "permission_denied"

    for method, path, payload in (
        (
            client.post,
            "/api/v1/catalog/order-comments/bulk",
            {"comments": "Sin cebolla", "product_ids": [BURGER_ID]},
        ),
        (
            client.put,
            f"/api/v1/catalog/order-comments/{comment_id}",
            {"text": "Sin hielo extra"},
        ),
        (
            client.put,
            f"/api/v1/catalog/order-comments/{comment_id}/products",
            {"product_ids": [BURGER_ID, FRIES_ID]},
        ),
    ):
        response = method(path, headers=branch_headers, json=payload)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "permission_denied"

    assert client.get(
        "/api/v1/catalog/order-comments", headers=_admin_headers()
    ).json()[0]["id"] == comment_id


def test_mixed_legacy_modifier_group_fails_closed_without_partial_deletion() -> None:
    client = _client_with_seeded_database()
    current = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin sal", "product_ids": [BURGER_ID]},
    )
    assert current.status_code == 200
    current_id = current.json()["items"][0]["id"]
    legacy = client.post(
        f"/api/v1/products/{BURGER_ID}/variation-notes",
        headers=_admin_headers(),
        json={"name": "Comentario que entró en conflicto"},
    )
    assert legacy.status_code == 200
    with _test_session_factory(client)() as session:
        session.execute(
            modifier_options.update()
            .where(modifier_options.c.id == legacy.json()["id"])
            .values(effect_type="instruction")
        )
        session.commit()

    rejected = client.delete(
        "/api/v1/catalog/order-comments/all",
        headers=_admin_headers(),
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "variation_group_conflict"
    with _test_session_factory(client)() as session:
        assert session.scalar(
            sa.select(sa.func.count()).select_from(order_comment_presets).where(
                order_comment_presets.c.id == current_id
            )
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count()).select_from(modifier_options).where(
                modifier_options.c.id == legacy.json()["id"]
            )
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count()).select_from(audit_events).where(
                audit_events.c.action.in_(
                    (
                        "order_comment.deleted",
                        "variation_note.legacy_deleted",
                        "variation_note.legacy_group_deleted",
                    )
                )
            )
        ) == 0


def test_global_comment_snapshot_is_frozen_without_inventory_or_price_effect() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin azúcar", "product_ids": [BURGER_ID]},
    ).json()
    comment_id = applied["items"][0]["id"]
    assert (
        _open_shift(client, 10000).status_code
        == 200
    )
    unrelated = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": SODA_ID,
                    "quantity": 1,
                    "comment_preset_ids": [comment_id],
                }
            ]
        },
    )
    assert unrelated.status_code == 409
    assert unrelated.json()["detail"]["code"] == "comment_preset_not_found"
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": BURGER_ID,
                    "quantity": 1,
                    "comment_preset_ids": [comment_id],
                }
            ]
        },
    )
    assert order.status_code == 200
    payload = order.json()
    snapshot = payload["consumption_snapshots"][0]
    comment = next(item for item in snapshot["modifiers"] if item["kind"] == "order_comment")
    assert comment["comment_preset_id"] == comment_id
    assert comment["kitchen_text"] == "Sin azúcar"
    assert comment["price_delta_cents"] == 0
    assert comment["inventory_effect"] is False
    assert payload["lines"][0]["modifier_total_cents"] == 0
    assert client.delete(
        f"/api/v1/catalog/order-comments/{comment_id}",
        headers=_admin_headers(),
    ).status_code == 200
    historical = client.get(
        f"/api/v1/orders/{payload['id']}",
        headers=_admin_headers(),
    )
    assert historical.status_code == 200
    frozen = next(
        modifier
        for modifier in historical.json()["lines"][0]["selected_modifiers"]
        if modifier["kind"] == "order_comment"
    )
    assert frozen["comment_preset_id"] == comment_id
    assert frozen["kitchen_text"] == "Sin azúcar"


def test_universal_extra_uses_canonical_backend_values_without_product_assignment() -> None:
    client = _client_with_seeded_database()
    forbidden = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID, "branch_id": BRANCH_ID},
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "global_catalog_branch_override"
    incomplete = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "ingredient_extra_configuration_required"
    extra = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={
            "inventory_item_id": BEEF_ID,
            "add_label": "Aguacate extra",
            "portion_quantity": "10.500000",
            "sale_price_cents": 250,
            "station": "kitchen",
            "display_order": 2,
        },
    )
    assert extra.status_code == 200
    extra_payload = extra.json()
    assert extra_payload["sale_price_cents"] == 250
    assert str(extra_payload["portion_quantity"]) == "10.500000"
    assert (
        client.get(
            "/api/v1/catalog/ingredient-extras/available",
            headers=_admin_headers(),
        ).json()[0]["extra_id"]
        == extra_payload["id"]
    )
    orphan = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "ingredient_extras": [{"extra_id": extra_payload["id"], "portions": 1}],
            "lines": [],
        },
    )
    assert orphan.status_code == 409
    assert orphan.json()["detail"]["code"] == "order_line_modifiers_required"

    assert (
        _open_shift(client, 10000).status_code
        == 200
    )
    invalid_portions = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 1,
                    "ingredient_extras": [{"extra_id": extra_payload["id"], "portions": 1.5}],
                }
            ],
        },
    )
    assert invalid_portions.status_code == 409
    assert invalid_portions.json()["detail"]["code"] == "invalid_ingredient_extra_portions"
    for portions in (0, -1, 100):
        rejected = client.post(
            "/api/v1/orders",
            headers=_admin_headers(),
            json={
                "lines": [
                    {
                        "product_id": FRIES_ID,
                        "quantity": 1,
                        "ingredient_extras": [
                            {"extra_id": extra_payload["id"], "portions": portions}
                        ],
                    }
                ]
            },
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "invalid_ingredient_extra_portions"
    duplicate = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 1,
                    "ingredient_extras": [
                        {"extra_id": extra_payload["id"], "portions": 1},
                        {"extra_id": extra_payload["id"], "portions": 1},
                    ],
                }
            ]
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_modifier_option"
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 1,
                    "ingredient_extras": [
                        {
                            "extra_id": extra_payload["id"],
                            "portions": 2,
                            "price_cents": 999999,
                        }
                    ],
                }
            ]
        },
    )
    assert order.status_code == 200
    payload = order.json()
    assert payload["total_cents"] == 4500 + 500
    extra_snapshot = next(
        item
        for item in payload["consumption_snapshots"][0]["modifiers"]
        if item["kind"] == "ingredient_extra"
    )
    assert extra_snapshot["extra_id"] == extra_payload["id"]
    assert extra_snapshot["portion_count"] == 2
    assert str(extra_snapshot["add_quantity"]) == "21.000000"
    assert extra_snapshot["price_delta_cents"] == 500
    assert any(
        component["item_id"] == BEEF_ID and str(component["gross_quantity"]) == "21.000000"
        for component in payload["consumption_snapshots"][0]["components"]
    )

    quantity_two = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 2,
                    "ingredient_extras": [
                        {"extra_id": extra_payload["id"], "portions": 2, "price_cents": 1}
                    ],
                }
            ]
        },
    )
    assert quantity_two.status_code == 200
    quantity_two_payload = quantity_two.json()
    assert quantity_two_payload["total_cents"] == (4500 * 2) + (250 * 2 * 2)
    assert quantity_two_payload["lines"][0]["modifier_total_cents"] == 1000
    quantity_two_snapshot = quantity_two_payload["consumption_snapshots"][0]
    quantity_two_extra = next(
        modifier
        for modifier in quantity_two_snapshot["modifiers"]
        if modifier["kind"] == "ingredient_extra"
    )
    assert quantity_two_extra["portion_count"] == 2
    assert str(quantity_two_extra["add_quantity"]) == "42.000000"
    quantity_two_component = next(
        component
        for component in quantity_two_snapshot["components"]
        if component["item_id"] == BEEF_ID
    )
    assert str(quantity_two_component["gross_quantity"]) == "42.000000"
    assert Decimal(str(quantity_two_component["total_cost"])) == (
        Decimal(str(quantity_two_component["unit_cost"])) * Decimal("42.000000")
    )
    reservation = client.get(
        f"/api/v1/inventory/kardex?item_id={BEEF_ID}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_RESERVATION"
        and Decimal(str(row["quantity_delta"])) == Decimal("-42.000000")
        for row in reservation
    )
    task_id = quantity_two_payload["production_tasks"][0]["id"]
    kds_task = next(
        task
        for task in client.get("/api/v1/kds/tasks", headers=_admin_headers()).json()
        if task["id"] == task_id
    )
    assert any(
        modifier.get("extra_id") == extra_payload["id"]
        and str(modifier.get("add_quantity")) == "42.000000"
        for modifier in kds_task["selected_modifiers"]
    )
    paid = client.post(
        f"/api/v1/orders/{quantity_two_payload['id']}/payments",
        headers=_admin_headers(),
        json={
            "amount_cents": quantity_two_payload["total_cents"],
            "method": "cash",
            "register_id": "CAJA-01",
        },
    )
    assert paid.status_code == 200
    kitchen_print = next(
        job for job in client.get("/api/v1/print-jobs", headers=_admin_headers()).json()
        if job["order_id"] == quantity_two_payload["id"] and job["job_type"] == "kitchen"
    )
    assert any(
        modifier.get("extra_id") == extra_payload["id"]
        and str(modifier.get("add_quantity")) == "42.000000"
        for modifier in kitchen_print["payload"]["lines"][0]["selected_modifiers"]
    )
    assert client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        headers=_admin_headers(),
        json={"status": "IN_PROGRESS"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        headers=_admin_headers(),
        json={"status": "COMPLETED"},
    ).status_code == 200
    consumption = client.get(
        f"/api/v1/inventory/kardex?item_id={BEEF_ID}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_CONSUMPTION"
        and Decimal(str(row["quantity_delta"])) == Decimal("-42.000000")
        for row in consumption
    )

    for status in ("needs_review", "archived"):
        if status == "archived":
            assert client.put(
                f"/api/v1/catalog/ingredient-variations/{extra_payload['id']}",
                headers=_admin_headers(),
                json={"status": "active"},
            ).status_code == 200
        assert client.put(
            f"/api/v1/catalog/ingredient-variations/{extra_payload['id']}",
            headers=_admin_headers(),
            json={"status": status},
        ).status_code == 200
        available = client.get(
            "/api/v1/catalog/ingredient-extras/available", headers=_admin_headers()
        ).json()
        assert extra_payload["id"] not in {row["extra_id"] for row in available}
        unavailable = client.post(
            "/api/v1/orders",
            headers=_admin_headers(),
            json={
                "lines": [
                    {
                        "product_id": FRIES_ID,
                        "quantity": 1,
                        "ingredient_extras": [{"extra_id": extra_payload["id"], "portions": 1}],
                    }
                ]
            },
        )
        assert unavailable.status_code == 409
        assert unavailable.json()["detail"]["code"] == "ingredient_extra_not_found"

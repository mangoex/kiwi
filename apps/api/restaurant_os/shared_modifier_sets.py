"""Corporate modifier configurations shared by an explicit product scope."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.modifier_configuration import (
    _key,
    _normalize_groups,
    _require_corporate_catalog,
)
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    _acquire_idempotency_lock,
    _active_recipe_components,
    _audit,
    _id,
    _modifier_inventory_scope,
    _now,
    _sanitize_for_json,
)


def _digest(request: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _replay(
    session: Session, actor: str, key: str, request: dict[str, Any]
) -> dict[str, Any] | None:
    _acquire_idempotency_lock(session, "modifier-set-command", key)
    command = (
        session.execute(
            sa.select(models.modifier_set_configuration_commands).where(
                models.modifier_set_configuration_commands.c.organization_id == ORGANIZATION_ID,
                models.modifier_set_configuration_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if not command:
        return None
    if command["actor_user_id"] != actor or command["request_hash"] != _digest(request):
        raise BusinessError(
            "modifier_set_idempotency_conflict", "Idempotency key payload differs"
        )
    return {**dict(command["result"]), "result": "replay"}


def _record_command(
    session: Session,
    actor: str,
    modifier_set_id: str,
    key: str,
    request: dict[str, Any],
    result: dict[str, Any],
) -> None:
    session.execute(
        models.modifier_set_configuration_commands.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            actor_user_id=actor,
            modifier_set_id=modifier_set_id,
            idempotency_key=key,
            request_hash=_digest(request),
            result=result,
            created_at=_now(),
        )
    )


def _normalized_product_ids(product_ids: Any) -> list[str]:
    if not isinstance(product_ids, list) or not product_ids:
        raise BusinessError(
            "modifier_set_products_required", "At least one product is required"
        )
    normalized = [str(product_id).strip() for product_id in product_ids]
    if any(not product_id for product_id in normalized) or len(normalized) != len(set(normalized)):
        raise BusinessError(
            "modifier_set_products_invalid", "Product IDs must be non-empty and unique"
        )
    return normalized


def _product_rows(session: Session, product_ids: Any) -> list[dict[str, Any]]:
    normalized = _normalized_product_ids(product_ids)
    rows = list(
        session.execute(
            sa.select(models.products)
            .where(
                models.products.c.id.in_(normalized),
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.status == "active",
                models.products.c.catalog_scope == "organization",
            )
            .with_for_update()
        ).mappings()
    )
    if len(rows) != len(normalized):
        raise BusinessError(
            "modifier_set_product_not_found",
            "Every assigned product must be active and corporate",
        )
    stations = {str(row["station"]) for row in rows}
    if len(stations) != 1:
        raise BusinessError(
            "modifier_set_station_mismatch",
            "Shared modifier products must use the same production station",
        )
    by_id = {str(row["id"]): dict(row) for row in rows}
    return [by_id[product_id] for product_id in normalized]


def _lock_product_scope(session: Session, product_ids: list[str]) -> None:
    for product_id in sorted(product_ids):
        _acquire_idempotency_lock(session, "product-composition-mode", product_id)
    for product_id in sorted(product_ids):
        _acquire_idempotency_lock(session, "shared-modifier-product", product_id)


def _assert_products_support_shared_modifiers(
    session: Session, products: list[dict[str, Any]]
) -> None:
    product_ids = [str(product["id"]) for product in products]
    fixed_combo = session.scalar(
        sa.select(models.product_compositions.c.combo_product_id)
        .where(
            models.product_compositions.c.combo_product_id.in_(product_ids),
            models.product_compositions.c.organization_id == ORGANIZATION_ID,
            models.product_compositions.c.status == "active",
        )
        .limit(1)
    )
    component_product = session.scalar(
        sa.select(models.modifier_options.c.component_product_id)
        .select_from(
            models.modifier_options.join(
                models.modifier_groups,
                models.modifier_groups.c.id == models.modifier_options.c.group_id,
            )
        )
        .where(
            models.modifier_options.c.component_product_id.in_(product_ids),
            models.modifier_options.c.status == "active",
            models.modifier_groups.c.organization_id == ORGANIZATION_ID,
            models.modifier_groups.c.status == "active",
        )
        .limit(1)
    )
    fixed_combo_component = session.scalar(
        sa.select(models.product_composition_components.c.product_id)
        .select_from(
            models.product_composition_components.join(
                models.product_compositions,
                models.product_compositions.c.id
                == models.product_composition_components.c.composition_id,
            )
        )
        .where(
            models.product_composition_components.c.product_id.in_(product_ids),
            models.product_compositions.c.organization_id == ORGANIZATION_ID,
            models.product_compositions.c.status == "active",
        )
        .limit(1)
    )
    if fixed_combo or fixed_combo_component or component_product:
        raise BusinessError(
            "modifier_set_product_composition_conflict",
            "Fixed combos and selectable component products keep product-specific authority",
        )


def _assert_inventory_effects_apply_to_scope(
    session: Session,
    products: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> None:
    required_effects = {"remove", "quantity", "substitute", "variant"}
    affected_items = {
        str(option["affected_item_id"])
        for group in groups
        for option in group.get("options", [])
        if option.get("inventory_effect")
        and option.get("effect_type") in required_effects
        and option.get("affected_item_id")
    }
    if not affected_items:
        return
    for product in products:
        recipe_items = {
            str(component["item_id"])
            for component in _active_recipe_components(session, str(product["id"]))
        }
        if not affected_items.issubset(recipe_items):
            raise BusinessError(
                "modifier_set_recipe_incompatible",
                "Every affected item must exist in every assigned product recipe",
            )


def _set_row(session: Session, modifier_set_id: str, *, lock: bool = False) -> dict[str, Any]:
    query = sa.select(models.modifier_sets).where(
        models.modifier_sets.c.id == modifier_set_id,
        models.modifier_sets.c.organization_id == ORGANIZATION_ID,
        models.modifier_sets.c.status == "active",
    )
    if lock:
        query = query.with_for_update()
    row = session.execute(query).mappings().first()
    if not row:
        raise BusinessError("modifier_set_not_found", "Modifier set was not found")
    return dict(row)


def _assigned_products(session: Session, modifier_set_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in session.execute(
            sa.select(
                models.products.c.id,
                models.products.c.name,
                models.products.c.sku,
                models.products.c.category_id,
                models.products.c.station,
            )
            .select_from(
                models.modifier_set_products.join(
                    models.products,
                    models.products.c.id == models.modifier_set_products.c.product_id,
                )
            )
            .where(
                models.modifier_set_products.c.modifier_set_id == modifier_set_id,
                models.modifier_set_products.c.status == "active",
                models.products.c.status == "active",
            )
            .order_by(models.products.c.name, models.products.c.sku)
        ).mappings()
    ]


def _groups_view(session: Session, modifier_set_id: str) -> list[dict[str, Any]]:
    groups = list(
        session.execute(
            sa.select(models.modifier_groups)
            .where(
                models.modifier_groups.c.modifier_set_id == modifier_set_id,
                models.modifier_groups.c.organization_id == ORGANIZATION_ID,
                models.modifier_groups.c.status == "active",
            )
            .order_by(models.modifier_groups.c.display_order, models.modifier_groups.c.name)
        ).mappings()
    )
    by_id = {str(row["id"]): {**dict(row), "options": []} for row in groups}
    if by_id:
        for row in session.execute(
            sa.select(models.modifier_options)
            .where(
                models.modifier_options.c.group_id.in_(by_id),
                models.modifier_options.c.status == "active",
            )
            .order_by(models.modifier_options.c.display_order, models.modifier_options.c.name)
        ).mappings():
            by_id[str(row["group_id"])]["options"].append(dict(row))
    return cast(list[dict[str, Any]], _sanitize_for_json(list(by_id.values())))


def _set_view(session: Session, row: dict[str, Any]) -> dict[str, Any]:
    products = _assigned_products(session, str(row["id"]))
    return cast(
        dict[str, Any],
        _sanitize_for_json(
            {
                "id": row["id"],
                "name": row["name"],
                "version": int(row["version"]),
                "station": row["station"],
                "status": row["status"],
                "products": products,
                "group_count": len(_groups_view(session, str(row["id"]))),
            }
        ),
    )


def list_modifier_sets(session: Session, actor_user_id: str) -> list[dict[str, Any]]:
    _require_corporate_catalog(session, actor_user_id)
    rows = session.execute(
        sa.select(models.modifier_sets)
        .where(
            models.modifier_sets.c.organization_id == ORGANIZATION_ID,
            models.modifier_sets.c.status == "active",
        )
        .order_by(models.modifier_sets.c.name)
    ).mappings()
    return [_set_view(session, dict(row)) for row in rows]


def create_modifier_set(
    session: Session,
    actor_user_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    actor = _require_corporate_catalog(session, actor_user_id)
    if set(payload) - {"name", "product_ids"}:
        raise BusinessError("modifier_set_unknown_field", "Modifier set contains unknown fields")
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 120:
        raise BusinessError("modifier_set_invalid", "Modifier set name is required")
    product_ids = _normalized_product_ids(payload.get("product_ids"))
    key = _key(idempotency_key)
    request = {"operation": "create", "name": name, "product_ids": product_ids}
    replay = _replay(session, actor, key, request)
    if replay:
        return replay
    _lock_product_scope(session, product_ids)
    products = _product_rows(session, product_ids)
    _assert_products_support_shared_modifiers(session, products)
    if session.scalar(
        sa.select(models.modifier_sets.c.id).where(
            models.modifier_sets.c.organization_id == ORGANIZATION_ID,
            models.modifier_sets.c.name == name,
        )
    ):
        raise BusinessError("modifier_set_name_conflict", "Modifier set name already exists")
    now = _now()
    modifier_set_id = _id()
    session.execute(
        models.modifier_sets.insert().values(
            id=modifier_set_id,
            organization_id=ORGANIZATION_ID,
            name=name,
            version=1,
            station=products[0]["station"],
            status="active",
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.modifier_set_products.insert(),
        [
            {
                "modifier_set_id": modifier_set_id,
                "product_id": product["id"],
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            for product in products
        ],
    )
    result = {**_set_view(session, _set_row(session, modifier_set_id)), "result": "applied"}
    _record_command(session, actor, modifier_set_id, key, request, result)
    _audit(
        session,
        "modifier_set.created",
        "modifier_set",
        modifier_set_id,
        {"version": 1, "product_count": len(products)},
        actor_user_id=actor,
    )
    session.commit()
    return result


def get_modifier_set_configuration(
    session: Session, actor_user_id: str, modifier_set_id: str
) -> dict[str, Any]:
    _require_corporate_catalog(session, actor_user_id)
    row = _set_row(session, modifier_set_id)
    products = _assigned_products(session, modifier_set_id)
    if not products:
        raise BusinessError("modifier_set_products_required", "Modifier set has no active products")
    reference = _product_rows(session, [products[0]["id"]])[0]
    inventory_candidates = [
        dict(item)
        for item in session.execute(
            sa.select(
                models.inventory_items.c.id,
                models.inventory_items.c.name,
                models.inventory_items.c.sku,
                models.inventory_units.c.code.label("unit_code"),
            )
            .join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
            )
            .where(
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
                _modifier_inventory_scope(
                    reference["catalog_scope"], reference["source_branch_id"]
                ),
            )
            .order_by(models.inventory_items.c.name, models.inventory_items.c.sku)
        ).mappings()
    ]
    return cast(
        dict[str, Any],
        _sanitize_for_json(
            {
                "product": {
                    "id": modifier_set_id,
                    "name": row["name"],
                    "sku": "COMPARTIDO",
                    "station": row["station"],
                },
                "expected_version": int(row["version"]),
                "groups": _groups_view(session, modifier_set_id),
                "component_candidates": [],
                "inventory_candidates": inventory_candidates,
                "products": products,
            }
        ),
    )


def save_modifier_set_configuration(
    session: Session,
    actor_user_id: str,
    modifier_set_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    actor = _require_corporate_catalog(session, actor_user_id)
    if set(payload) - {"expected_version", "groups"}:
        raise BusinessError("modifier_set_unknown_field", "Configuration contains unknown fields")
    expected_version = payload.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise BusinessError("modifier_configuration_invalid", "Expected version is invalid")
    raw_groups = payload.get("groups")
    if isinstance(raw_groups, list) and any(
        isinstance(group, dict)
        and isinstance(group.get("options"), list)
        and any(
            isinstance(option, dict) and option.get("effect_type") == "product_component"
            for option in group["options"]
        )
        for group in raw_groups
    ):
        raise BusinessError(
            "shared_modifier_component_forbidden",
            "Product components remain configured on each product",
        )
    key = _key(idempotency_key)
    request = {"operation": "configuration", "modifier_set_id": modifier_set_id, **payload}
    replay = _replay(session, actor, key, request)
    if replay:
        return replay
    _acquire_idempotency_lock(session, "modifier-set", modifier_set_id)
    row = _set_row(session, modifier_set_id, lock=True)
    if int(row["version"]) != expected_version:
        raise BusinessError(
            "modifier_set_version_conflict", "Modifier set changed in another session"
        )
    assigned_products = _assigned_products(session, modifier_set_id)
    product_ids = [str(product["id"]) for product in assigned_products]
    _lock_product_scope(session, product_ids)
    products = _product_rows(session, product_ids)
    _assert_products_support_shared_modifiers(session, products)
    reference = products[0]
    normalized = _normalize_groups(session, reference, raw_groups)
    _assert_inventory_effects_apply_to_scope(session, products, normalized)
    existing_groups = {
        str(group["id"]): dict(group)
        for group in session.execute(
            sa.select(models.modifier_groups).where(
                models.modifier_groups.c.modifier_set_id == modifier_set_id,
                models.modifier_groups.c.status == "active",
            )
        ).mappings()
    }
    now = _now()
    retained_groups: set[str] = set()
    for group in normalized:
        group_id = group["id"] or _id()
        if group["id"] and group_id not in existing_groups:
            raise BusinessError("modifier_group_not_found", "Modifier group was not found")
        duplicate = session.execute(
            sa.select(models.modifier_groups).where(
                models.modifier_groups.c.modifier_set_id == modifier_set_id,
                models.modifier_groups.c.name == group["name"],
                models.modifier_groups.c.id != group_id,
            )
        ).mappings().first()
        if duplicate:
            if group["id"] or duplicate["status"] != "archived":
                raise BusinessError("modifier_group_name_conflict", "Modifier group name exists")
            group_id = str(duplicate["id"])
            existing_groups[group_id] = dict(duplicate)
        retained_groups.add(group_id)
        group_values = {
            field: group[field]
            for field in (
                "name", "is_required", "minimum_selections", "maximum_selections",
                "included_selections", "station", "display_order",
            )
        }
        if group_id in existing_groups:
            session.execute(
                models.modifier_groups.update()
                .where(models.modifier_groups.c.id == group_id)
                .values(**group_values, status="active", updated_at=now)
            )
        else:
            session.execute(
                models.modifier_groups.insert().values(
                    id=group_id,
                    organization_id=ORGANIZATION_ID,
                    product_id=None,
                    modifier_set_id=modifier_set_id,
                    **group_values,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
        existing_options = {
            str(option["id"]): dict(option)
            for option in session.execute(
                sa.select(models.modifier_options).where(
                    models.modifier_options.c.group_id == group_id,
                    models.modifier_options.c.status == "active",
                )
            ).mappings()
        }
        retained_options: set[str] = set()
        for option in group["options"]:
            option_id = option["id"] or _id()
            if option["id"] and option_id not in existing_options:
                raise BusinessError("modifier_option_not_found", "Modifier option was not found")
            duplicate_option = session.execute(
                sa.select(models.modifier_options).where(
                    models.modifier_options.c.group_id == group_id,
                    models.modifier_options.c.name == option["name"],
                    models.modifier_options.c.id != option_id,
                )
            ).mappings().first()
            if duplicate_option:
                if option["id"] or duplicate_option["status"] != "archived":
                    raise BusinessError(
                        "modifier_option_name_conflict", "Modifier option name exists"
                    )
                option_id = str(duplicate_option["id"])
                existing_options[option_id] = dict(duplicate_option)
            retained_options.add(option_id)
            option_values = {
                field: option[field]
                for field in (
                    "name", "effect_type", "price_delta_cents", "component_product_id",
                    "component_quantity", "affected_item_id", "replacement_item_id",
                    "remove_quantity", "add_quantity", "inventory_effect", "kitchen_text",
                    "station", "display_order",
                )
            }
            if option_id in existing_options:
                session.execute(
                    models.modifier_options.update()
                    .where(models.modifier_options.c.id == option_id)
                    .values(**option_values, status="active", updated_at=now)
                )
            else:
                session.execute(
                    models.modifier_options.insert().values(
                        id=option_id,
                        group_id=group_id,
                        **option_values,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
        removed_options = set(existing_options) - retained_options
        if removed_options:
            session.execute(
                models.modifier_options.update().where(
                    models.modifier_options.c.id.in_(removed_options)
                ).values(status="archived", updated_at=now)
            )
    removed_groups = set(existing_groups) - retained_groups
    if removed_groups:
        session.execute(
            models.modifier_options.update().where(
                models.modifier_options.c.group_id.in_(removed_groups)
            ).values(status="archived", updated_at=now)
        )
        session.execute(
            models.modifier_groups.update().where(
                models.modifier_groups.c.id.in_(removed_groups)
            ).values(status="archived", updated_at=now)
        )
    next_version = int(row["version"]) + 1
    session.execute(
        models.modifier_sets.update().where(models.modifier_sets.c.id == modifier_set_id).values(
            version=next_version, updated_by=actor, updated_at=now
        )
    )
    result = {
        "version": next_version,
        "groups": _groups_view(session, modifier_set_id),
        "result": "applied",
    }
    _record_command(session, actor, modifier_set_id, key, request, result)
    _audit(
        session,
        "modifier_set.configuration_updated",
        "modifier_set",
        modifier_set_id,
        {"version": next_version, "group_count": len(normalized)},
        actor_user_id=actor,
    )
    session.commit()
    return result


def replace_modifier_set_products(
    session: Session,
    actor_user_id: str,
    modifier_set_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    actor = _require_corporate_catalog(session, actor_user_id)
    if set(payload) - {"expected_version", "product_ids"}:
        raise BusinessError("modifier_set_unknown_field", "Product scope contains unknown fields")
    expected_version = payload.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise BusinessError("modifier_configuration_invalid", "Expected version is invalid")
    product_ids = _normalized_product_ids(payload.get("product_ids"))
    key = _key(idempotency_key)
    request = {
        "operation": "products",
        "modifier_set_id": modifier_set_id,
        "expected_version": expected_version,
        "product_ids": product_ids,
    }
    replay = _replay(session, actor, key, request)
    if replay:
        return replay
    _acquire_idempotency_lock(session, "modifier-set", modifier_set_id)
    row = _set_row(session, modifier_set_id, lock=True)
    if int(row["version"]) != expected_version:
        raise BusinessError(
            "modifier_set_version_conflict", "Modifier set changed in another session"
        )
    _lock_product_scope(session, product_ids)
    products = _product_rows(session, product_ids)
    _assert_products_support_shared_modifiers(session, products)
    if str(row["station"]) != str(products[0]["station"]):
        raise BusinessError(
            "modifier_set_station_mismatch", "Assigned products must keep the set station"
        )
    _assert_inventory_effects_apply_to_scope(
        session, products, _groups_view(session, modifier_set_id)
    )
    now = _now()
    existing = {
        str(item["product_id"]): dict(item)
        for item in session.execute(
            sa.select(models.modifier_set_products).where(
                models.modifier_set_products.c.modifier_set_id == modifier_set_id
            )
        ).mappings()
    }
    desired = {str(product["id"]) for product in products}
    for product_id in desired:
        if product_id in existing:
            session.execute(
                models.modifier_set_products.update().where(
                    models.modifier_set_products.c.modifier_set_id == modifier_set_id,
                    models.modifier_set_products.c.product_id == product_id,
                ).values(status="active", updated_at=now)
            )
        else:
            session.execute(
                models.modifier_set_products.insert().values(
                    modifier_set_id=modifier_set_id,
                    product_id=product_id,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
    removed = set(existing) - desired
    if removed:
        session.execute(
            models.modifier_set_products.update().where(
                models.modifier_set_products.c.modifier_set_id == modifier_set_id,
                models.modifier_set_products.c.product_id.in_(removed),
            ).values(status="archived", updated_at=now)
        )
    next_version = int(row["version"]) + 1
    session.execute(
        models.modifier_sets.update().where(models.modifier_sets.c.id == modifier_set_id).values(
            version=next_version, updated_by=actor, updated_at=now
        )
    )
    result = {
        "id": modifier_set_id,
        "version": next_version,
        "products": _assigned_products(session, modifier_set_id),
        "result": "applied",
    }
    _record_command(session, actor, modifier_set_id, key, request, result)
    _audit(
        session,
        "modifier_set.products_replaced",
        "modifier_set",
        modifier_set_id,
        {
            "version": next_version,
            "product_count": len(desired),
            "added_count": len(desired - set(existing)),
            "removed_count": len(removed),
        },
        actor_user_id=actor,
    )
    session.commit()
    return result

"""Versioned administrative configuration for selectable compound products."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _acquire_idempotency_lock,
    _actor_has_organization_scope,
    _actor_user_id,
    _audit,
    _id,
    _modifier_catalog_is_managed_elsewhere,
    _now,
    _quantity,
    _sanitize_for_json,
    require_permission,
)

_ALLOWED_EFFECTS = {
    "remove",
    "add",
    "substitute",
    "quantity",
    "variant",
    "instruction",
    "product_component",
}
_GROUP_KEYS = {
    "id",
    "name",
    "is_required",
    "minimum_selections",
    "maximum_selections",
    "included_selections",
    "station",
    "options",
}
_OPTION_KEYS = {
    "id",
    "name",
    "effect_type",
    "price_delta_cents",
    "component_product_id",
    "component_quantity",
    "affected_item_id",
    "replacement_item_id",
    "remove_quantity",
    "add_quantity",
    "inventory_effect",
    "kitchen_text",
    "station",
}


def _key(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BusinessError(
            "modifier_configuration_idempotency_key_required", "Idempotency-Key is required"
        )
    if len(normalized) > 180:
        raise BusinessError(
            "modifier_configuration_idempotency_key_invalid",
            "Idempotency-Key exceeds 180 characters",
        )
    return normalized


def _whole_quantity(value: Any) -> Decimal:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError(
            "modifier_component_quantity_invalid",
            "Component quantity must be a positive whole product unit",
        ) from exc
    if (
        not quantity.is_finite()
        or quantity <= 0
        or quantity != quantity.to_integral_value()
        or quantity > Decimal("999999")
    ):
        raise BusinessError(
            "modifier_component_quantity_invalid",
            "Component quantity must be a positive whole product unit",
        )
    return quantity.quantize(Decimal("0.000001"))


def _cardinality(value: Any, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > 2_147_483_647
    ):
        raise BusinessError("invalid_modifier_group", f"{field} must be an integer")
    return int(value)


def _require_corporate_catalog(session: Session, actor_user_id: str) -> str:
    actor = _actor_user_id(actor_user_id)
    if not _actor_has_organization_scope(session, actor):
        raise AuthorizationError(
            "modifier_configuration_corporate_scope_required",
            "Corporate catalog authority is required",
        )
    require_permission(session, actor, "catalog.manage", None)
    return actor


def _requested_component_product_ids(raw_groups: Any) -> set[str]:
    if not isinstance(raw_groups, list):
        return set()
    component_ids: set[str] = set()
    for raw_group in raw_groups:
        if not isinstance(raw_group, dict) or not isinstance(raw_group.get("options"), list):
            continue
        for raw_option in raw_group["options"]:
            if not isinstance(raw_option, dict):
                continue
            if str(raw_option.get("effect_type", "")).strip().lower() != "product_component":
                continue
            component_id = str(raw_option.get("component_product_id") or "").strip()
            if component_id:
                component_ids.add(component_id)
    return component_ids


def _product(session: Session, product_id: str) -> dict[str, Any]:
    product = (
        session.execute(
            sa.select(models.products).where(
                models.products.c.id == product_id,
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if not product:
        raise BusinessError("product_not_found", "Product was not found")
    return dict(product)


def _manageable_groups(session: Session, product_id: str) -> list[dict[str, Any]]:
    rows = list(
        session.execute(
            sa.select(models.modifier_groups)
            .where(
                models.modifier_groups.c.product_id == product_id,
                models.modifier_groups.c.organization_id == ORGANIZATION_ID,
                models.modifier_groups.c.status == "active",
            )
            .order_by(models.modifier_groups.c.display_order, models.modifier_groups.c.name)
        ).mappings()
    )
    return [
        dict(row)
        for row in rows
        if not _modifier_catalog_is_managed_elsewhere(session, group_id=str(row["id"]))
    ]


def _has_selectable_groups(session: Session, product_id: str) -> bool:
    group_ids = session.scalars(
        sa.select(models.modifier_groups.c.id).where(
            models.modifier_groups.c.product_id == product_id,
            models.modifier_groups.c.organization_id == ORGANIZATION_ID,
            models.modifier_groups.c.status == "active",
        )
    )
    return any(
        not _modifier_catalog_is_managed_elsewhere(session, group_id=str(group_id))
        for group_id in group_ids
    )


def _groups_view(session: Session, product_id: str) -> list[dict[str, Any]]:
    groups = _manageable_groups(session, product_id)
    if not groups:
        return []
    by_id = {str(group["id"]): {**group, "options": []} for group in groups}
    options = session.execute(
        sa.select(models.modifier_options)
        .where(
            models.modifier_options.c.group_id.in_(by_id),
            models.modifier_options.c.status == "active",
        )
        .order_by(models.modifier_options.c.display_order, models.modifier_options.c.name)
    ).mappings()
    for row in options:
        by_id[str(row["group_id"])]["options"].append(dict(row))
    return [_sanitize_for_json(group) for group in by_id.values()]


def _component_candidates(session: Session, parent: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = session.execute(
        sa.select(models.products.c.id, models.products.c.name, models.products.c.sku)
        .where(
            models.products.c.organization_id == ORGANIZATION_ID,
            models.products.c.status == "active",
            models.products.c.catalog_scope == "organization",
            models.products.c.station == parent["station"],
            models.products.c.id != parent["id"],
            sa.exists(
                sa.select(models.recipes.c.id).where(
                    models.recipes.c.product_id == models.products.c.id,
                    models.recipes.c.organization_id == ORGANIZATION_ID,
                    models.recipes.c.status == "active",
                    models.recipes.c.valid_to.is_(None),
                )
            ),
            ~sa.exists(
                sa.select(models.product_compositions.c.id).where(
                    models.product_compositions.c.combo_product_id == models.products.c.id,
                    models.product_compositions.c.organization_id == ORGANIZATION_ID,
                    models.product_compositions.c.status == "active",
                )
            ),
        )
        .order_by(models.products.c.name, models.products.c.sku)
    ).mappings()
    return [
        dict(row)
        for row in candidates
        if not _has_selectable_groups(session, product_id=str(row["id"]))
    ]


def get_modifier_configuration(
    session: Session, actor_user_id: str, product_id: str
) -> dict[str, Any]:
    _require_corporate_catalog(session, actor_user_id)
    product = _product(session, product_id)
    version = session.scalar(
        sa.select(models.product_modifier_configurations.c.version).where(
            models.product_modifier_configurations.c.product_id == product_id,
            models.product_modifier_configurations.c.organization_id == ORGANIZATION_ID,
        )
    )
    return cast(
        dict[str, Any],
        _sanitize_for_json(
            {
                "product": {
                    "id": product["id"],
                    "name": product["name"],
                    "sku": product["sku"],
                    "station": product["station"],
                },
                "expected_version": int(version or 0),
                "groups": _groups_view(session, product_id),
                "component_candidates": _component_candidates(session, product),
            },
        ),
    )


def _validate_component(
    session: Session, parent: dict[str, Any], component_product_id: str
) -> dict[str, Any]:
    if component_product_id == parent["id"]:
        raise BusinessError("modifier_component_self_reference", "A product cannot contain itself")
    component = (
        session.execute(
            sa.select(models.products).where(
                models.products.c.id == component_product_id,
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if not component or component["catalog_scope"] != "organization":
        raise BusinessError(
            "modifier_component_out_of_scope", "Component product is not corporate and active"
        )
    if component["station"] != parent["station"]:
        raise BusinessError(
            "modifier_component_station_mismatch",
            "Component product must use the same production station",
        )
    if session.scalar(
        sa.select(models.product_compositions.c.id)
        .where(
            models.product_compositions.c.combo_product_id == component_product_id,
            models.product_compositions.c.organization_id == ORGANIZATION_ID,
            models.product_compositions.c.status == "active",
        )
        .limit(1)
    ):
        raise BusinessError("modifier_component_nested", "Fixed combos cannot be selected")
    if _has_selectable_groups(session, component_product_id):
        raise BusinessError(
            "modifier_component_nested", "Selectable products cannot contain modifier groups"
        )
    if not session.scalar(
        sa.select(models.recipes.c.id)
        .where(
            models.recipes.c.product_id == component_product_id,
            models.recipes.c.organization_id == ORGANIZATION_ID,
            models.recipes.c.status == "active",
            models.recipes.c.valid_to.is_(None),
        )
        .limit(1)
    ):
        raise BusinessError(
            "modifier_component_recipe_required", "Component product requires an active recipe"
        )
    return dict(component)


def _normalize_option(
    session: Session,
    parent: dict[str, Any],
    raw: Any,
    display_order: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise BusinessError("modifier_configuration_invalid", "Options must be objects")
    unknown = set(raw) - _OPTION_KEYS
    if unknown:
        raise BusinessError(
            "modifier_configuration_unknown_field", f"Unknown option fields: {sorted(unknown)}"
        )
    effect = str(raw.get("effect_type", "instruction")).strip().lower()
    name = str(raw.get("name", "")).strip()
    if effect not in _ALLOWED_EFFECTS or not name or len(name) > 120:
        raise BusinessError("invalid_modifier_option", "Modifier option fields are invalid")
    price = raw.get("price_delta_cents", 0)
    if (
        isinstance(price, bool)
        or not isinstance(price, int)
        or price < 0
        or price > 2_147_483_647
    ):
        raise BusinessError(
            "invalid_modifier_price", "Modifier price must be representable cents >= 0"
        )
    affected = raw.get("affected_item_id") or None
    replacement = raw.get("replacement_item_id") or None
    try:
        remove_quantity = _quantity(raw.get("remove_quantity", 0))
        add_quantity = _quantity(raw.get("add_quantity", 0))
    except (InvalidOperation, ValueError):
        raise BusinessError(
            "invalid_modifier_option", "Modifier quantities must be valid decimals"
        ) from None
    if not remove_quantity.is_finite() or not add_quantity.is_finite():
        raise BusinessError("invalid_modifier_option", "Modifier quantities must be finite")
    component_product_id = str(raw.get("component_product_id") or "").strip() or None
    component_quantity: Decimal | None = None
    component: dict[str, Any] | None = None
    if effect == "product_component":
        if not component_product_id or affected or replacement:
            raise BusinessError(
                "modifier_component_product_required",
                "Product component requires only a component product",
            )
        component_quantity = _whole_quantity(raw.get("component_quantity", 1))
        component = _validate_component(session, parent, component_product_id)
        remove_quantity = Decimal("0")
        add_quantity = Decimal("0")
    elif component_product_id or raw.get("component_quantity") not in (None, ""):
        raise BusinessError(
            "modifier_component_fields_forbidden",
            "Only product components may reference a product",
        )
    if effect in {"remove", "quantity", "substitute", "variant"} and not affected:
        raise BusinessError("modifier_affected_item_required", "Modifier requires an affected item")
    if effect in {"substitute", "variant"} and not replacement:
        raise BusinessError(
            "modifier_replacement_item_required", "Substitution requires a replacement item"
        )
    if effect == "add" and not (affected or replacement):
        raise BusinessError("modifier_added_item_required", "Add modifier requires an item")
    item_ids = [str(item_id) for item_id in (affected, replacement) if item_id]
    if item_ids:
        found = set(
            session.scalars(
                sa.select(models.inventory_items.c.id).where(
                    models.inventory_items.c.id.in_(item_ids),
                    models.inventory_items.c.organization_id == ORGANIZATION_ID,
                    models.inventory_items.c.status == "active",
                )
            )
        )
        if found != set(item_ids):
            raise BusinessError("modifier_item_not_found", "Modifier inventory item was not found")
    kitchen_text = str(raw.get("kitchen_text") or name).strip()
    if not kitchen_text or len(kitchen_text) > 240:
        raise BusinessError(
            "invalid_modifier_option", "Kitchen text must contain at most 240 characters"
        )
    return {
        "id": str(raw.get("id") or "").strip() or None,
        "name": name,
        "effect_type": effect,
        "price_delta_cents": price,
        "component_product_id": component_product_id,
        "component_product_name": component["name"] if component else None,
        "component_quantity": component_quantity,
        "affected_item_id": affected,
        "replacement_item_id": replacement,
        "remove_quantity": remove_quantity,
        "add_quantity": add_quantity,
        "inventory_effect": effect not in {"instruction"},
        "kitchen_text": kitchen_text,
        "station": str(parent["station"]),
        "display_order": display_order,
    }


def _normalize_groups(
    session: Session, parent: dict[str, Any], raw_groups: Any
) -> list[dict[str, Any]]:
    if not isinstance(raw_groups, list):
        raise BusinessError("modifier_configuration_invalid", "Groups must be an array")
    normalized: list[dict[str, Any]] = []
    group_names: set[str] = set()
    for group_index, raw in enumerate(raw_groups):
        if not isinstance(raw, dict):
            raise BusinessError("modifier_configuration_invalid", "Groups must be objects")
        unknown = set(raw) - _GROUP_KEYS
        if unknown:
            raise BusinessError(
                "modifier_configuration_unknown_field", f"Unknown group fields: {sorted(unknown)}"
            )
        name = str(raw.get("name", "")).strip()
        if not name or len(name) > 120 or name.casefold() in group_names:
            raise BusinessError("modifier_group_name_conflict", "Group names must be unique")
        group_names.add(name.casefold())
        minimum = _cardinality(raw.get("minimum_selections", 0), "minimum_selections")
        maximum = _cardinality(raw.get("maximum_selections", 1), "maximum_selections")
        included = _cardinality(raw.get("included_selections", 0), "included_selections")
        required_raw = raw.get("is_required", minimum > 0)
        if not isinstance(required_raw, bool):
            raise BusinessError("invalid_modifier_group", "is_required must be boolean")
        required = required_raw
        options_raw = raw.get("options", [])
        if (
            minimum < 0
            or maximum < 1
            or minimum > maximum
            or included < 0
            or included > maximum
            or (required and minimum < 1)
            or not isinstance(options_raw, list)
            or minimum > len(options_raw)
        ):
            raise BusinessError("invalid_modifier_group", "Group cardinality is invalid")
        options = [
            _normalize_option(session, parent, option, option_index)
            for option_index, option in enumerate(options_raw)
        ]
        option_names = [option["name"].casefold() for option in options]
        if len(option_names) != len(set(option_names)):
            raise BusinessError("modifier_option_name_conflict", "Option names must be unique")
        normalized.append(
            {
                "id": str(raw.get("id") or "").strip() or None,
                "name": name,
                "is_required": required,
                "minimum_selections": minimum,
                "maximum_selections": maximum,
                "included_selections": included,
                "station": str(parent["station"]),
                "display_order": group_index,
                "options": options,
            }
        )
    return normalized


def save_modifier_configuration(
    session: Session,
    actor_user_id: str,
    product_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    actor = _require_corporate_catalog(session, actor_user_id)
    if set(payload) - {"expected_version", "groups"}:
        raise BusinessError(
            "modifier_configuration_unknown_field", "Configuration contains unknown fields"
        )
    expected_version = payload.get("expected_version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise BusinessError(
            "modifier_configuration_invalid", "Expected version must be a non-negative integer"
        )
    key = _key(idempotency_key)
    request = {"product_id": product_id, **payload}
    digest = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    _acquire_idempotency_lock(session, "modifier-configuration-command", key)
    existing_command = (
        session.execute(
            sa.select(models.modifier_configuration_commands).where(
                models.modifier_configuration_commands.c.organization_id == ORGANIZATION_ID,
                models.modifier_configuration_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if existing_command:
        if existing_command["actor_user_id"] != actor or existing_command["request_hash"] != digest:
            raise BusinessError(
                "modifier_configuration_idempotency_conflict",
                "Idempotency key payload differs",
            )
        return {**dict(existing_command["result"]), "result": "replay"}

    composition_product_ids = {product_id, *_requested_component_product_ids(payload.get("groups"))}
    for composition_product_id in sorted(composition_product_ids):
        _acquire_idempotency_lock(session, "product-composition-mode", composition_product_id)
    _acquire_idempotency_lock(session, "modifier-configuration", product_id)
    parent_row = (
        session.execute(
            sa.select(models.products)
            .where(
                models.products.c.id == product_id,
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.status == "active",
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not parent_row:
        raise BusinessError("product_not_found", "Product was not found")
    parent = dict(parent_row)
    header = (
        session.execute(
            sa.select(models.product_modifier_configurations)
            .where(
                models.product_modifier_configurations.c.product_id == product_id,
                models.product_modifier_configurations.c.organization_id == ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    current_version = int(header["version"]) if header else 0
    if current_version != expected_version:
        raise BusinessError(
            "modifier_configuration_version_conflict",
            "Modifier configuration changed in another session",
        )
    normalized = _normalize_groups(session, parent, payload.get("groups"))
    if normalized and session.scalar(
        sa.select(models.product_compositions.c.id)
        .where(
            models.product_compositions.c.combo_product_id == product_id,
            models.product_compositions.c.organization_id == ORGANIZATION_ID,
            models.product_compositions.c.status == "active",
        )
        .limit(1)
    ):
        raise BusinessError(
            "modifier_component_nested",
            "A fixed combo cannot also be a selectable compound product",
        )
    if normalized and session.scalar(
        sa.select(models.modifier_options.c.id)
        .select_from(
            models.modifier_options.join(
                models.modifier_groups,
                models.modifier_groups.c.id == models.modifier_options.c.group_id,
            )
        )
        .where(
            models.modifier_options.c.component_product_id == product_id,
            models.modifier_options.c.status == "active",
            models.modifier_groups.c.organization_id == ORGANIZATION_ID,
            models.modifier_groups.c.status == "active",
        )
        .limit(1)
    ):
        raise BusinessError(
            "modifier_component_nested",
            "A product already used as a component cannot contain selectable groups",
        )
    existing_groups = {str(row["id"]): dict(row) for row in _manageable_groups(session, product_id)}
    now = _now()
    retained_group_ids: set[str] = set()
    for group in normalized:
        group_id = group["id"] or _id()
        if group["id"] and group_id not in existing_groups:
            raise BusinessError("modifier_group_not_found", "Modifier group was not found")
        stored_group_with_name = (
            session.execute(
                sa.select(models.modifier_groups).where(
                    models.modifier_groups.c.product_id == product_id,
                    models.modifier_groups.c.name == group["name"],
                    models.modifier_groups.c.id != group_id,
                )
            )
            .mappings()
            .first()
        )
        if stored_group_with_name:
            if group["id"] or stored_group_with_name["status"] != "archived":
                raise BusinessError(
                    "modifier_group_name_conflict",
                    "Modifier group name already exists",
                )
            if _modifier_catalog_is_managed_elsewhere(
                session, group_id=str(stored_group_with_name["id"])
            ):
                raise BusinessError(
                    "modifier_group_name_conflict",
                    "Modifier group name belongs to another catalog",
                )
            group_id = str(stored_group_with_name["id"])
            existing_groups[group_id] = dict(stored_group_with_name)
        if not group["id"]:
            active_group_with_name = next(
                (
                    row
                    for row in existing_groups.values()
                    if row["name"] == group["name"] and str(row["id"]) != group_id
                ),
                None,
            )
            if active_group_with_name:
                raise BusinessError(
                    "modifier_group_name_conflict",
                    "Modifier group name already exists",
                )
        retained_group_ids.add(group_id)
        values = {
            key_name: group[key_name]
            for key_name in (
                "name",
                "is_required",
                "minimum_selections",
                "maximum_selections",
                "included_selections",
                "station",
                "display_order",
            )
        }
        if group_id in existing_groups:
            session.execute(
                models.modifier_groups.update()
                .where(models.modifier_groups.c.id == group_id)
                .values(**values, status="active", updated_at=now)
            )
        else:
            session.execute(
                models.modifier_groups.insert().values(
                    id=group_id,
                    organization_id=ORGANIZATION_ID,
                    product_id=product_id,
                    **values,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
        existing_options = {
            str(row["id"]): dict(row)
            for row in session.execute(
                sa.select(models.modifier_options).where(
                    models.modifier_options.c.group_id == group_id,
                    models.modifier_options.c.status == "active",
                )
            ).mappings()
        }
        retained_option_ids: set[str] = set()
        for option in group["options"]:
            option_id = option["id"] or _id()
            if option["id"] and option_id not in existing_options:
                raise BusinessError("modifier_option_not_found", "Modifier option was not found")
            stored_option_with_name = (
                session.execute(
                    sa.select(models.modifier_options).where(
                        models.modifier_options.c.group_id == group_id,
                        models.modifier_options.c.name == option["name"],
                        models.modifier_options.c.id != option_id,
                    )
                )
                .mappings()
                .first()
            )
            if stored_option_with_name:
                if option["id"] or stored_option_with_name["status"] != "archived":
                    raise BusinessError(
                        "modifier_option_name_conflict",
                        "Modifier option name already exists",
                    )
                option_id = str(stored_option_with_name["id"])
                existing_options[option_id] = dict(stored_option_with_name)
            retained_option_ids.add(option_id)
            option_values = {
                key_name: option[key_name]
                for key_name in (
                    "name",
                    "effect_type",
                    "price_delta_cents",
                    "component_product_id",
                    "component_quantity",
                    "affected_item_id",
                    "replacement_item_id",
                    "remove_quantity",
                    "add_quantity",
                    "inventory_effect",
                    "kitchen_text",
                    "station",
                    "display_order",
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
        removed_options = set(existing_options) - retained_option_ids
        if removed_options:
            session.execute(
                models.modifier_options.update()
                .where(models.modifier_options.c.id.in_(removed_options))
                .values(status="archived", updated_at=now)
            )
    removed_groups = set(existing_groups) - retained_group_ids
    if removed_groups:
        session.execute(
            models.modifier_options.update()
            .where(models.modifier_options.c.group_id.in_(removed_groups))
            .values(status="archived", updated_at=now)
        )
        session.execute(
            models.modifier_groups.update()
            .where(models.modifier_groups.c.id.in_(removed_groups))
            .values(status="archived", updated_at=now)
        )
    next_version = current_version + 1
    if header:
        session.execute(
            models.product_modifier_configurations.update()
            .where(models.product_modifier_configurations.c.product_id == product_id)
            .values(version=next_version, updated_by=actor, updated_at=now)
        )
    else:
        session.execute(
            models.product_modifier_configurations.insert().values(
                product_id=product_id,
                organization_id=ORGANIZATION_ID,
                version=next_version,
                updated_by=actor,
                updated_at=now,
            )
        )
    result = cast(
        dict[str, Any],
        _sanitize_for_json(
            {
                "version": next_version,
                "groups": _groups_view(session, product_id),
                "result": "applied",
            }
        ),
    )
    session.execute(
        models.modifier_configuration_commands.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            actor_user_id=actor,
            product_id=product_id,
            idempotency_key=key,
            request_hash=digest,
            result=result,
            created_at=now,
        )
    )
    _audit(
        session,
        "modifier_configuration.updated",
        "product",
        product_id,
        {"version": next_version, "group_count": len(normalized)},
        branch_id=None,
        actor_user_id=actor,
    )
    session.commit()
    return result

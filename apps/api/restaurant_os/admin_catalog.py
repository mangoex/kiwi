"""Deterministic administrative catalog commands for ADMIN-RETRO-001.

The module deliberately owns only additive Admin configuration and coordinates recipe
version writes without calling the legacy single-recipe command, which commits per product.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    BRANCH_ID,
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _acquire_idempotency_lock,
    _actor_user_id,
    _audit,
    _branch_warehouse_id,
    _id,
    _normalize_recipe_components,
    _now,
    _physical_inventory_quantity,
    _quantity,
    _sanitize_for_json,
    actor_has_organization_authority,
    authorize_branch_scope,
    require_permission,
)

logger = logging.getLogger(__name__)


def _record_admin_catalog_metric(
    metric: str,
    *,
    result: str,
    started_at: float,
    scope_kind: str,
    destination_count: int | None = None,
    usage_count: int | None = None,
    command_id: str | None = None,
    error_code: str | None = None,
    race_path: str | None = None,
) -> None:
    """Emit bounded operational telemetry without catalog or identity data."""
    extra: dict[str, Any] = {
        "metric": metric,
        "result": result,
        "duration_ms": int((perf_counter() - started_at) * 1000),
        "scope": scope_kind,
    }
    if destination_count is not None:
        extra["destination_count"] = destination_count
    if usage_count is not None:
        extra["usage_count"] = usage_count
    if command_id is not None:
        extra["command_id"] = command_id
    if error_code is not None:
        extra["error_code"] = error_code
    if race_path is not None:
        extra["race_path"] = race_path
    logger.info(metric, extra=extra)


def _admin_catalog_error_result(error: BusinessError) -> str:
    if isinstance(error, AuthorizationError):
        return "denied"
    if error.code.endswith("_conflict"):
        return "conflict"
    return "error"


def _active_categories(session: Session) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in session.execute(
            sa.select(models.product_categories)
            .where(
                models.product_categories.c.organization_id == ORGANIZATION_ID,
                models.product_categories.c.status == "active",
            )
            .order_by(
                models.product_categories.c.display_order,
                models.product_categories.c.name,
                models.product_categories.c.id,
            )
        ).mappings()
    ]


def _priority_view(
    categories: list[dict[str, Any]], category_ids: list[str]
) -> list[dict[str, Any]]:
    names = {str(category["id"]): str(category["name"]) for category in categories}
    return [
        {"id": category_id, "name": names[category_id], "position": index + 1}
        for index, category_id in enumerate(category_ids)
    ]


def _require_corporate_catalog(session: Session, actor_user_id: str) -> str:
    actor_id = _actor_user_id(actor_user_id)
    if not actor_has_organization_authority(session, actor_id):
        raise AuthorizationError(
            "admin_catalog_corporate_scope_required",
            "Corporate catalog authority is required",
        )
    require_permission(session, actor_id, "catalog.manage", None)
    return str(actor_id)


def get_category_priorities(session: Session, actor_user_id: str) -> dict[str, Any]:
    _require_corporate_catalog(session, actor_user_id)
    categories = _active_categories(session)
    default_ids = [str(category["id"]) for category in categories]
    config = (
        session.execute(
            sa.select(models.admin_category_priority_configs).where(
                models.admin_category_priority_configs.c.organization_id == ORGANIZATION_ID
            )
        )
        .mappings()
        .first()
    )
    view_ids = _reconcile_priority_ids(default_ids, config["view_category_ids"] if config else [])
    print_ids = _reconcile_priority_ids(default_ids, config["print_category_ids"] if config else [])
    return {
        "version": int(config["version"]) if config else 0,
        "view_order": _priority_view(categories, view_ids),
        "print_order": _priority_view(categories, print_ids),
    }


def _reconcile_priority_ids(default_ids: list[str], stored_ids: Any) -> list[str]:
    """Project saved order onto the current active set without mutating configuration."""
    active = set(default_ids)
    retained: list[str] = []
    for raw_id in stored_ids if isinstance(stored_ids, list) else []:
        category_id = str(raw_id)
        if category_id in active and category_id not in retained:
            retained.append(category_id)
    return retained + [category_id for category_id in default_ids if category_id not in retained]


def _validate_priority_ids(categories: list[dict[str, Any]], candidate: list[str]) -> list[str]:
    expected = {str(category["id"]) for category in categories}
    normalized = [str(value) for value in candidate]
    if len(normalized) != len(set(normalized)):
        raise BusinessError("category_priorities_repeated", "Category priority IDs cannot repeat")
    if set(normalized) != expected:
        raise BusinessError(
            "category_priorities_incomplete",
            "Category priority IDs must contain every active category exactly once",
        )
    return normalized


def set_category_priorities(
    session: Session,
    actor_user_id: str,
    *,
    view_category_ids: list[str],
    print_category_ids: list[str],
    expected_version: int,
) -> dict[str, Any]:
    actor_id = _require_corporate_catalog(session, actor_user_id)
    if expected_version < 0:
        raise BusinessError("category_priorities_version_invalid", "Expected version is invalid")
    categories = _active_categories(session)
    view_ids = _validate_priority_ids(categories, view_category_ids)
    print_ids = _validate_priority_ids(categories, print_category_ids)
    _acquire_idempotency_lock(session, "admin-category-priorities", ORGANIZATION_ID)
    config = (
        session.execute(
            sa.select(models.admin_category_priority_configs)
            .where(models.admin_category_priority_configs.c.organization_id == ORGANIZATION_ID)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    current_version = int(config["version"]) if config else 0
    if expected_version != current_version:
        raise BusinessError("category_priorities_version_conflict", "Category priorities changed")
    now = _now()
    new_version = current_version + 1
    try:
        if config:
            session.execute(
                sa.update(models.admin_category_priority_configs)
                .where(models.admin_category_priority_configs.c.organization_id == ORGANIZATION_ID)
                .values(
                    view_category_ids=view_ids,
                    print_category_ids=print_ids,
                    version=new_version,
                    updated_by=actor_id,
                    updated_at=now,
                )
            )
        else:
            session.execute(
                models.admin_category_priority_configs.insert().values(
                    organization_id=ORGANIZATION_ID,
                    view_category_ids=view_ids,
                    print_category_ids=print_ids,
                    version=new_version,
                    created_by=actor_id,
                    updated_by=actor_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        _audit(
            session,
            "admin_category_priorities.updated",
            "admin_category_priority_config",
            ORGANIZATION_ID,
            {"version": new_version},
            branch_id=None,
            actor_user_id=actor_id,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessError(
            "category_priorities_version_conflict", "Category priorities changed"
        ) from exc
    return {
        "version": new_version,
        "view_order": _priority_view(categories, view_ids),
        "print_order": _priority_view(categories, print_ids),
    }


def _exact_nonnegative(value: Any, field: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError("stock_threshold_invalid", f"{field} must be a decimal") from exc
    if not decimal_value.is_finite() or decimal_value < 0:
        raise BusinessError(
            "stock_threshold_invalid", f"{field} must be a finite non-negative decimal"
        )
    # NUMERIC(18, 6) is the persistence contract.  Reject rather than round a
    # client value so a threshold never silently changes at the boundary.
    exponent = decimal_value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -6:
        raise BusinessError(
            "stock_threshold_precision_invalid",
            f"{field} supports at most six decimal places",
        )
    integral = format(decimal_value, "f").split(".", maxsplit=1)[0].lstrip("0")
    if len(integral) > 12:
        raise BusinessError(
            "stock_threshold_range_invalid",
            f"{field} exceeds NUMERIC(18, 6)",
        )
    try:
        return Decimal(str(_quantity(decimal_value)))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError("stock_threshold_invalid", f"{field} must be a decimal") from exc


def _inventory_item_in_scope(session: Session, item_id: str, branch_id: str) -> dict[str, Any]:
    item = (
        session.execute(
            sa.select(models.inventory_items).where(
                models.inventory_items.c.id == item_id,
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
                models.inventory_items.c.item_type == "ingredient",
                sa.or_(
                    models.inventory_items.c.catalog_scope == "organization",
                    models.inventory_items.c.source_branch_id == branch_id,
                ),
            )
        )
        .mappings()
        .first()
    )
    if not item:
        raise BusinessError("stock_threshold_item_not_found", "Active ingredient was not found")
    return dict(item)


def _threshold_row(
    session: Session, branch_id: str, warehouse_id: str, item_id: str, *, lock: bool = False
) -> dict[str, Any] | None:
    query = sa.select(models.inventory_stock_thresholds).where(
        models.inventory_stock_thresholds.c.organization_id == ORGANIZATION_ID,
        models.inventory_stock_thresholds.c.branch_id == branch_id,
        models.inventory_stock_thresholds.c.warehouse_id == warehouse_id,
        models.inventory_stock_thresholds.c.item_id == item_id,
    )
    if lock:
        query = query.with_for_update()
    row = session.execute(query).mappings().first()
    return dict(row) if row else None


def set_stock_threshold(
    session: Session,
    actor_user_id: str,
    branch_id: str,
    item_id: str,
    *,
    minimum_quantity: Any,
    maximum_quantity: Any,
    expected_version: int | None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    authorized_branch = authorize_branch_scope(session, actor_id, "catalog.manage", branch_id)
    if not authorized_branch:
        raise AuthorizationError("stock_threshold_branch_required", "A branch is required")
    minimum = _exact_nonnegative(minimum_quantity, "minimum_quantity")
    maximum = _exact_nonnegative(maximum_quantity, "maximum_quantity")
    if maximum < minimum:
        raise BusinessError("stock_threshold_range_invalid", "Maximum cannot be lower than minimum")
    item = _inventory_item_in_scope(session, item_id, authorized_branch)
    warehouse_id = _branch_warehouse_id(session, authorized_branch)
    current = _threshold_row(session, authorized_branch, warehouse_id, item_id, lock=True)
    current_version = int(current["version"]) if current else 0
    if expected_version is None:
        version_matches = current is None
    else:
        version_matches = expected_version == current_version
    if not version_matches:
        raise BusinessError("stock_threshold_version_conflict", "Stock threshold changed")
    now = _now()
    version = current_version + 1
    try:
        if current:
            updated_id = session.execute(
                sa.update(models.inventory_stock_thresholds)
                .where(
                    models.inventory_stock_thresholds.c.id == current["id"],
                    models.inventory_stock_thresholds.c.version == current_version,
                )
                .values(
                    minimum_quantity=minimum,
                    maximum_quantity=maximum,
                    version=version,
                    updated_by=actor_id,
                    updated_at=now,
                )
                .returning(models.inventory_stock_thresholds.c.id)
            ).scalar_one_or_none()
            if updated_id is None:
                raise BusinessError("stock_threshold_version_conflict", "Stock threshold changed")
            threshold_id = str(updated_id)
        else:
            threshold_id = _id()
            session.execute(
                models.inventory_stock_thresholds.insert().values(
                    id=threshold_id,
                    organization_id=ORGANIZATION_ID,
                    branch_id=authorized_branch,
                    warehouse_id=warehouse_id,
                    item_id=item_id,
                    minimum_quantity=minimum,
                    maximum_quantity=maximum,
                    version=version,
                    created_by=actor_id,
                    updated_by=actor_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        _audit(
            session,
            "inventory_stock_threshold.updated",
            "inventory_stock_threshold",
            threshold_id,
            {"item_id": item["id"], "version": version},
            branch_id=authorized_branch,
            actor_user_id=actor_id,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessError("stock_threshold_version_conflict", "Stock threshold changed") from exc
    return {
        "id": threshold_id,
        "branch_id": authorized_branch,
        "warehouse_id": warehouse_id,
        "item_id": item_id,
        "minimum_quantity": minimum,
        "maximum_quantity": maximum,
        "version": version,
    }


def delete_stock_threshold(
    session: Session,
    actor_user_id: str,
    branch_id: str,
    item_id: str,
    expected_version: int,
) -> None:
    actor_id = _actor_user_id(actor_user_id)
    authorized_branch = authorize_branch_scope(session, actor_id, "catalog.manage", branch_id)
    if not authorized_branch:
        raise AuthorizationError("stock_threshold_branch_required", "A branch is required")
    warehouse_id = _branch_warehouse_id(session, authorized_branch)
    current = _threshold_row(session, authorized_branch, warehouse_id, item_id, lock=True)
    if not current:
        raise BusinessError("stock_threshold_not_found", "Stock threshold was not found")
    if int(current["version"]) != expected_version:
        raise BusinessError("stock_threshold_version_conflict", "Stock threshold changed")
    try:
        deleted_id = session.execute(
            sa.delete(models.inventory_stock_thresholds)
            .where(
                models.inventory_stock_thresholds.c.id == current["id"],
                models.inventory_stock_thresholds.c.version == expected_version,
            )
            .returning(models.inventory_stock_thresholds.c.id)
        ).scalar_one_or_none()
        if deleted_id is None:
            raise BusinessError("stock_threshold_version_conflict", "Stock threshold changed")
        _audit(
            session,
            "inventory_stock_threshold.removed",
            "inventory_stock_threshold",
            str(deleted_id),
            {"item_id": item_id, "version": expected_version},
            branch_id=authorized_branch,
            actor_user_id=actor_id,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessError("stock_threshold_version_conflict", "Stock threshold changed") from exc


def _canonical_stock(session: Session, branch_id: str, warehouse_id: str) -> dict[str, Decimal]:
    item_ids = session.execute(
        sa.select(models.inventory_items.c.id).where(
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.item_type == "ingredient",
            models.inventory_items.c.status == "active",
        )
    ).scalars()
    return {
        str(item_id): _physical_inventory_quantity(session, branch_id, warehouse_id, str(item_id))
        for item_id in item_ids
    }


def get_stock_thresholds(
    session: Session, actor_user_id: str, branch_id: str
) -> list[dict[str, Any]]:
    actor_id = _actor_user_id(actor_user_id)
    authorized_branch = authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
    if not authorized_branch:
        raise AuthorizationError("stock_threshold_branch_required", "A branch is required")
    warehouse_id = _branch_warehouse_id(session, authorized_branch)
    stocks = _canonical_stock(session, authorized_branch, warehouse_id)
    threshold_rows = session.execute(
        sa.select(models.inventory_stock_thresholds).where(
            models.inventory_stock_thresholds.c.organization_id == ORGANIZATION_ID,
            models.inventory_stock_thresholds.c.branch_id == authorized_branch,
            models.inventory_stock_thresholds.c.warehouse_id == warehouse_id,
        )
    ).mappings()
    thresholds = {str(row["item_id"]): dict(row) for row in threshold_rows}
    items = session.execute(
        sa.select(
            models.inventory_items.c.id,
            models.inventory_items.c.name,
            models.inventory_units.c.id.label("unit_id"),
            models.inventory_units.c.code.label("unit_code"),
        )
        .select_from(
            models.inventory_items.join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
            )
        )
        .where(
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.item_type == "ingredient",
            models.inventory_items.c.status == "active",
            sa.or_(
                models.inventory_items.c.catalog_scope == "organization",
                models.inventory_items.c.source_branch_id == authorized_branch,
            ),
        )
        .order_by(models.inventory_items.c.name, models.inventory_items.c.id)
    ).mappings()
    as_of = _now()
    response: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item["id"])
        threshold = thresholds.get(item_id)
        quantity = stocks.get(item_id, Decimal("0.000000"))
        if not threshold:
            status = "no_thresholds"
            minimum = maximum = version = None
        else:
            minimum = _quantity(threshold["minimum_quantity"])
            maximum = _quantity(threshold["maximum_quantity"])
            version = int(threshold["version"])
            status = (
                "below_minimum"
                if quantity < minimum
                else "above_maximum"
                if quantity > maximum
                else "in_range"
            )
        response.append(
            {
                "item_id": item_id,
                "item_name": item["name"],
                "branch_id": authorized_branch,
                "warehouse_id": warehouse_id,
                "unit_id": str(item["unit_id"]),
                "unit_code": item["unit_code"],
                "quantity_on_hand": quantity,
                "minimum_quantity": minimum,
                "maximum_quantity": maximum,
                "version": version,
                "status": status,
                "as_of": as_of,
            }
        )
    return response


def _recipe_scope(
    session: Session, actor_user_id: str, branch_id: str | None
) -> tuple[str, str | None]:
    actor_id = _actor_user_id(actor_user_id)
    if branch_id is None:
        if not actor_has_organization_authority(session, actor_id):
            raise AuthorizationError(
                "recipe_branch_required", "A branch is required for this actor"
            )
        require_permission(session, actor_id, "recipes.manage", BRANCH_ID)
        return actor_id, None
    return actor_id, authorize_branch_scope(session, actor_id, "recipes.manage", branch_id)


def _validate_bulk_payload(
    session: Session, payload: dict[str, Any], branch_id: str | None
) -> dict[str, Any]:
    if not isinstance(payload, dict) or "components" not in payload:
        raise BusinessError("recipe_payload_invalid", "Recipe payload must include components")
    unsupported = set(payload) - {"yield_quantity", "yield_unit_id", "components"}
    if unsupported:
        raise BusinessError("recipe_payload_invalid", "Recipe payload has unsupported fields")
    try:
        raw_yield_quantity = Decimal(str(payload.get("yield_quantity", 1)))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError(
            "invalid_recipe_yield", "Recipe yield must be a finite decimal"
        ) from exc
    if not raw_yield_quantity.is_finite():
        raise BusinessError("invalid_recipe_yield", "Recipe yield must be finite")
    try:
        yield_quantity = _quantity(raw_yield_quantity)
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError("invalid_recipe_yield", "Recipe yield is outside precision") from exc
    if not yield_quantity.is_finite() or yield_quantity <= 0:
        raise BusinessError("invalid_recipe_yield", "Recipe yield must be positive")
    yield_unit_id = str(payload.get("yield_unit_id") or "")
    unit_exists = False
    if yield_unit_id:
        unit_exists = bool(
            session.execute(
                sa.select(models.inventory_units.c.id).where(
                    models.inventory_units.c.id == yield_unit_id,
                    models.inventory_units.c.organization_id == ORGANIZATION_ID,
                )
            ).scalar_one_or_none()
        )
    if not unit_exists:
        raise BusinessError("recipe_yield_unit_invalid", "Recipe yield unit is invalid")
    raw_components = payload["components"]
    if not isinstance(raw_components, list):
        raise BusinessError("recipe_payload_invalid", "Recipe components must be a list")
    for component in raw_components:
        if not isinstance(component, dict):
            raise BusinessError("recipe_component_invalid", "Recipe component must be an object")
        item_id = str(component.get("item_id") or "").strip()
        unit_id = str(component.get("unit_id") or "").strip()
        if not item_id or not unit_id:
            raise BusinessError(
                "recipe_component_invalid", "Recipe component item and unit are required"
            )
        raw_waste = component.get("waste_rate", 0)
        try:
            waste = Decimal(str(raw_waste))
        except (InvalidOperation, ValueError) as exc:
            raise BusinessError("recipe_waste_invalid", "Recipe waste must be a decimal") from exc
        if not waste.is_finite() or waste < 0 or waste >= 1:
            raise BusinessError(
                "recipe_waste_invalid", "Recipe waste must be from 0 inclusive to 1 exclusive"
            )
        item = (
            session.execute(
                sa.select(models.inventory_items.c.base_unit_id).where(
                    models.inventory_items.c.id == item_id,
                    models.inventory_items.c.organization_id == ORGANIZATION_ID,
                    models.inventory_items.c.status == "active",
                    sa.or_(
                        models.inventory_items.c.catalog_scope == "organization",
                        models.inventory_items.c.source_branch_id == branch_id,
                    ),
                )
            )
            .mappings()
            .first()
        )
        if not item:
            raise BusinessError("recipe_component_not_found", "Recipe component item was not found")
        if str(item["base_unit_id"]) != unit_id:
            raise BusinessError(
                "recipe_component_unit_mismatch", "Recipe component unit is incompatible"
            )
    components = _normalize_recipe_components(session, raw_components, branch_id=branch_id)
    return {
        "yield_quantity": yield_quantity,
        "yield_unit_id": yield_unit_id,
        "components": components,
    }


def _scoped_active_recipes(
    session: Session, product_ids: list[str], branch_id: str | None, *, lock: bool = False
) -> dict[str, dict[str, Any]]:
    query = sa.select(models.recipes).where(
        models.recipes.c.organization_id == ORGANIZATION_ID,
        models.recipes.c.product_id.in_(product_ids),
        models.recipes.c.recipe_type == "sale",
        models.recipes.c.status == "active",
        models.recipes.c.branch_id.is_(branch_id)
        if branch_id is None
        else models.recipes.c.branch_id == branch_id,
    )
    if lock:
        query = query.with_for_update()
    return {str(row["product_id"]): dict(row) for row in session.execute(query).mappings()}


def _validate_destinations(
    session: Session, product_ids: list[str], branch_id: str | None, *, lock: bool = False
) -> list[dict[str, Any]]:
    ids = [str(value) for value in product_ids]
    if not ids or len(ids) != len(set(ids)):
        raise BusinessError(
            "bulk_recipe_destinations_invalid", "Destinations must be unique and non-empty"
        )
    query = (
        sa.select(models.products)
        .where(
            models.products.c.organization_id == ORGANIZATION_ID,
            models.products.c.id.in_(ids),
            models.products.c.status == "active",
            sa.or_(
                models.products.c.catalog_scope == "organization",
                models.products.c.source_branch_id == branch_id,
            ),
        )
        .order_by(models.products.c.id)
    )
    if lock:
        query = query.with_for_update()
    products = [dict(row) for row in session.execute(query).mappings()]
    if len(products) != len(ids):
        raise BusinessError("bulk_recipe_destination_not_found", "A destination product is invalid")
    return products


def _bulk_fingerprint(
    branch_id: str | None, product_ids: list[str], normalized_payload: dict[str, Any]
) -> str:
    document = {
        "branch_id": branch_id,
        "destination_product_ids": sorted(str(value) for value in product_ids),
        "payload": _sanitize_for_json(normalized_payload),
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _recipe_components_for_diff(session: Session, recipe_id: str | None) -> list[dict[str, Any]]:
    if not recipe_id:
        return []
    return [
        {
            "item_id": str(row["item_id"]),
            "unit_id": str(row["unit_id"]),
            "net_quantity": _quantity(row["net_quantity"]),
            "waste_rate": _quantity(row["waste_rate"]),
            "gross_quantity": _quantity(row["gross_quantity"]),
        }
        for row in session.execute(
            sa.select(models.recipe_components)
            .where(models.recipe_components.c.recipe_id == recipe_id)
            .order_by(models.recipe_components.c.sort_order, models.recipe_components.c.item_id)
        ).mappings()
    ]


def preview_bulk_recipe(
    session: Session,
    actor_user_id: str,
    *,
    branch_id: str | None,
    destination_product_ids: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    _, scope = _recipe_scope(session, actor_user_id, branch_id)
    normalized = _validate_bulk_payload(session, payload, scope)
    products = _validate_destinations(session, destination_product_ids, scope)
    active = _scoped_active_recipes(session, [str(row["id"]) for row in products], scope)
    destinations = []
    for product in products:
        current = active.get(str(product["id"]))
        current_components = _recipe_components_for_diff(
            session, str(current["id"]) if current else None
        )
        next_components = [
            {
                "item_id": str(component["item_id"]),
                "unit_id": str(component["unit_id"]),
                "net_quantity": _quantity(component["net_quantity"]),
                "waste_rate": _quantity(component["waste_rate"]),
                "gross_quantity": _quantity(component["gross_quantity"]),
            }
            for component in normalized["components"]
        ]
        destinations.append(
            {
                "product_id": str(product["id"]),
                "expected_active_recipe_id": str(current["id"]) if current else None,
                "expected_version": int(current["version"]) if current else 0,
                "has_active_recipe": current is not None,
                "difference": {
                    "current_yield_quantity": current["yield_quantity"] if current else None,
                    "current_yield_unit_id": str(current["yield_unit_id"]) if current else None,
                    "current_components": current_components,
                    "next_yield_quantity": normalized["yield_quantity"],
                    "next_yield_unit_id": normalized["yield_unit_id"],
                    "next_components": next_components,
                    "changed": current is None
                    or current["yield_quantity"] != normalized["yield_quantity"]
                    or str(current["yield_unit_id"]) != normalized["yield_unit_id"]
                    or current_components != next_components,
                },
            }
        )
    return {
        "branch_id": scope,
        "fingerprint": _bulk_fingerprint(scope, destination_product_ids, normalized),
        "destinations": destinations,
        "normalized_payload": _sanitize_for_json(normalized),
    }


def _bulk_command_hash(preview: dict[str, Any], expected_ids: dict[str, str | None]) -> str:
    document = {
        "fingerprint": preview["fingerprint"],
        "expected_active_recipe_ids": {key: expected_ids[key] for key in sorted(expected_ids)},
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _bulk_request_hash(
    branch_id: str | None,
    destination_product_ids: list[str],
    payload: dict[str, Any],
    preview_fingerprint: str,
    expected_ids: dict[str, str | None],
) -> str:
    document = {
        "branch_id": branch_id,
        "destination_product_ids": sorted(str(value) for value in destination_product_ids),
        "payload": _sanitize_for_json(payload),
        "preview_fingerprint": preview_fingerprint,
        "expected_active_recipe_ids": {key: expected_ids[key] for key in sorted(expected_ids)},
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _apply_bulk_recipe(
    session: Session,
    actor_user_id: str,
    *,
    branch_id: str | None,
    destination_product_ids: list[str],
    payload: dict[str, Any],
    preview_fingerprint: str,
    expected_active_recipe_ids: dict[str, str | None],
    idempotency_key: str,
    record_outcome: Callable[[dict[str, Any], str, str | None], None],
) -> dict[str, Any]:
    actor_id, scope = _recipe_scope(session, actor_user_id, branch_id)
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise BusinessError("idempotency_key_required", "Idempotency-Key is required")
    expected = {
        str(key): (str(value) if value is not None else None)
        for key, value in expected_active_recipe_ids.items()
    }
    request_hash = _bulk_request_hash(
        scope, destination_product_ids, payload, preview_fingerprint, expected
    )
    _acquire_idempotency_lock(session, "admin-recipe-bulk", idempotency_key.strip())
    existing = (
        session.execute(
            sa.select(models.admin_recipe_bulk_commands).where(
                models.admin_recipe_bulk_commands.c.organization_id == ORGANIZATION_ID,
                models.admin_recipe_bulk_commands.c.idempotency_key == idempotency_key.strip(),
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if existing["actor_user_id"] != actor_id or existing["request_hash"] != request_hash:
            raise BusinessError(
                "idempotency_conflict", "Idempotency key belongs to another command"
            )
        replay = dict(existing["result"])
        record_outcome(replay, "replay", "stored_command")
        return replay
    normalized_for_replay = _validate_bulk_payload(session, payload, scope)
    _validate_destinations(session, destination_product_ids, scope)
    recomputed_fingerprint = _bulk_fingerprint(
        scope, destination_product_ids, normalized_for_replay
    )
    if preview_fingerprint != recomputed_fingerprint:
        raise BusinessError("bulk_recipe_preview_conflict", "Recipe preview is no longer current")
    preview = preview_bulk_recipe(
        session,
        actor_id,
        branch_id=scope,
        destination_product_ids=destination_product_ids,
        payload=payload,
    )
    if preview_fingerprint != preview["fingerprint"]:
        raise BusinessError("bulk_recipe_preview_conflict", "Recipe preview is no longer current")
    preview_expected = {
        row["product_id"]: row["expected_active_recipe_id"] for row in preview["destinations"]
    }
    if expected != preview_expected:
        raise BusinessError(
            "bulk_recipe_version_conflict", "Expected recipe versions do not match preview"
        )
    try:
        products = _validate_destinations(session, destination_product_ids, scope, lock=True)
        product_ids = [str(product["id"]) for product in products]
        active = _scoped_active_recipes(session, product_ids, scope, lock=True)
        actual = {
            product_id: (str(active[product_id]["id"]) if product_id in active else None)
            for product_id in product_ids
        }
        if actual != expected:
            raise BusinessError("bulk_recipe_version_conflict", "A destination recipe changed")
        normalized = _validate_bulk_payload(session, payload, scope)
        now = _now()
        destinations: list[dict[str, Any]] = []
        for product in products:
            product_id = str(product["id"])
            previous = active.get(product_id)
            version = (
                int(
                    session.execute(
                        sa.select(sa.func.coalesce(sa.func.max(models.recipes.c.version), 0)).where(
                            models.recipes.c.product_id == product_id
                        )
                    ).scalar_one()
                )
                + 1
            )
            recipe_id = _id()
            if previous:
                session.execute(
                    sa.update(models.recipes)
                    .where(models.recipes.c.id == previous["id"])
                    .values(status="retired", valid_to=now, updated_at=now)
                )
            recipe = {
                "id": recipe_id,
                "organization_id": ORGANIZATION_ID,
                "product_id": product_id,
                "output_item_id": None,
                "branch_id": scope,
                "recipe_type": "sale",
                "version": version,
                "status": "active",
                "yield_quantity": normalized["yield_quantity"],
                "yield_unit_id": normalized["yield_unit_id"],
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
                "updated_at": now,
            }
            session.execute(models.recipes.insert().values(**recipe))
            for component in normalized["components"]:
                session.execute(
                    models.recipe_components.insert().values(recipe_id=recipe_id, **component)
                )
            _audit(
                session,
                "recipe.bulk_versioned",
                "recipe",
                recipe_id,
                {"product_id": product_id, "version": version, "branch_id": scope},
                branch_id=scope,
                actor_user_id=actor_id,
            )
            destinations.append(
                {"product_id": product_id, "recipe_id": recipe_id, "recipe_version": version}
            )
        command_id = _id()
        result: dict[str, Any] = {
            "command_id": command_id,
            "branch_id": scope,
            "destinations": destinations,
        }
        session.execute(
            models.admin_recipe_bulk_commands.insert().values(
                id=command_id,
                organization_id=ORGANIZATION_ID,
                actor_user_id=actor_id,
                branch_id=scope,
                idempotency_key=idempotency_key.strip(),
                request_hash=request_hash,
                preview_fingerprint=preview["fingerprint"],
                result=_sanitize_for_json(result),
                created_at=now,
            )
        )
        _audit(
            session,
            "admin_recipe_bulk.applied",
            "admin_recipe_bulk_command",
            command_id,
            {"destination_count": len(destinations), "branch_id": scope},
            branch_id=scope,
            actor_user_id=actor_id,
        )
        session.commit()
        record_outcome(result, "success", None)
        return result
    except IntegrityError as exc:
        session.rollback()
        raced = (
            session.execute(
                sa.select(models.admin_recipe_bulk_commands).where(
                    models.admin_recipe_bulk_commands.c.organization_id == ORGANIZATION_ID,
                    models.admin_recipe_bulk_commands.c.idempotency_key == idempotency_key.strip(),
                )
            )
            .mappings()
            .first()
        )
        if raced and raced["actor_user_id"] == actor_id and raced["request_hash"] == request_hash:
            replay = dict(raced["result"])
            record_outcome(replay, "replay", "unique_command")
            return replay
        if raced:
            raise BusinessError(
                "idempotency_conflict", "Idempotency key belongs to another command"
            ) from exc
        raise
    except Exception:
        session.rollback()
        raise


def apply_bulk_recipe(
    session: Session,
    actor_user_id: str,
    *,
    branch_id: str | None,
    destination_product_ids: list[str],
    payload: dict[str, Any],
    preview_fingerprint: str,
    expected_active_recipe_ids: dict[str, str | None],
    idempotency_key: str,
) -> dict[str, Any]:
    started_at = perf_counter()
    scope_kind = "corporate" if branch_id is None else "branch"
    destination_count = (
        len(destination_product_ids) if isinstance(destination_product_ids, list) else 0
    )

    def record_outcome(result: dict[str, Any], outcome: str, race_path: str | None) -> None:
        _record_admin_catalog_metric(
            "admin_catalog.bulk_recipe",
            result=outcome,
            started_at=started_at,
            scope_kind=scope_kind,
            destination_count=len(result.get("destinations", [])),
            command_id=str(result.get("command_id") or "") or None,
            race_path=race_path,
        )

    try:
        return _apply_bulk_recipe(
            session,
            actor_user_id,
            branch_id=branch_id,
            destination_product_ids=destination_product_ids,
            payload=payload,
            preview_fingerprint=preview_fingerprint,
            expected_active_recipe_ids=expected_active_recipe_ids,
            idempotency_key=idempotency_key,
            record_outcome=record_outcome,
        )
    except BusinessError as error:
        _record_admin_catalog_metric(
            "admin_catalog.bulk_recipe",
            result=_admin_catalog_error_result(error),
            started_at=started_at,
            scope_kind=scope_kind,
            destination_count=destination_count,
            error_code=error.code,
        )
        raise
    except Exception:
        _record_admin_catalog_metric(
            "admin_catalog.bulk_recipe",
            result="error",
            started_at=started_at,
            scope_kind=scope_kind,
            destination_count=destination_count,
            error_code="unexpected_error",
        )
        raise


def _get_recipe_usages(
    session: Session, actor_user_id: str, item_id: str, branch_id: str | None
) -> list[dict[str, Any]]:
    _, scope = _recipe_scope(session, actor_user_id, branch_id)
    item = session.execute(
        sa.select(models.inventory_items.c.id).where(
            models.inventory_items.c.id == item_id,
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.status == "active",
            sa.or_(
                models.inventory_items.c.catalog_scope == "organization",
                models.inventory_items.c.source_branch_id == scope,
            ),
        )
    ).scalar_one_or_none()
    if not item:
        raise BusinessError("recipe_usage_item_not_found", "Inventory item was not found")
    recipes_query = (
        sa.select(models.recipes)
        .join(models.products, models.products.c.id == models.recipes.c.product_id)
        .where(
            models.recipes.c.organization_id == ORGANIZATION_ID,
            models.recipes.c.recipe_type == "sale",
            models.recipes.c.status == "active",
            models.products.c.organization_id == ORGANIZATION_ID,
            models.products.c.status == "active",
            sa.or_(
                models.products.c.catalog_scope == "organization",
                models.products.c.source_branch_id == scope,
            ),
            models.recipes.c.branch_id.is_(None)
            if scope is None
            else sa.or_(models.recipes.c.branch_id == scope, models.recipes.c.branch_id.is_(None)),
        )
    )
    candidates = [dict(row) for row in session.execute(recipes_query).mappings()]
    effective: dict[str, dict[str, Any]] = {}
    for recipe in candidates:
        product_id = str(recipe["product_id"])
        if recipe["branch_id"] == scope:
            effective[product_id] = recipe
        elif product_id not in effective:
            effective[product_id] = recipe
    selected_recipe_ids = [str(recipe["id"]) for recipe in effective.values()]
    if not selected_recipe_ids:
        return []
    rows = session.execute(
        sa.select(
            models.recipes.c.product_id,
            models.products.c.name.label("product_name"),
            models.products.c.sku.label("product_sku"),
            models.recipes.c.id.label("recipe_id"),
            models.recipes.c.version.label("recipe_version"),
            models.recipe_components.c.item_id,
            models.recipe_components.c.quantity_base_units,
            models.recipe_components.c.unit_id,
            models.inventory_units.c.code.label("unit_code"),
        )
        .select_from(
            models.recipes.join(
                models.recipe_components,
                models.recipes.c.id == models.recipe_components.c.recipe_id,
            )
            .join(models.products, models.products.c.id == models.recipes.c.product_id)
            .join(
                models.inventory_units,
                models.inventory_units.c.id == models.recipe_components.c.unit_id,
            )
        )
        .where(
            models.recipes.c.id.in_(selected_recipe_ids),
            models.recipe_components.c.item_id == item_id,
        )
        .order_by(models.recipes.c.product_id, models.recipes.c.version)
    ).mappings()
    return [
        {
            "product_id": str(row["product_id"]),
            "product_name": row["product_name"],
            "product_sku": row["product_sku"],
            "recipe_id": str(row["recipe_id"]),
            "recipe_version": int(row["recipe_version"]),
            "item_id": str(row["item_id"]),
            "quantity_base_units": _quantity(row["quantity_base_units"]),
            "unit_id": str(row["unit_id"]),
            "unit_code": row["unit_code"],
        }
        for row in rows
    ]


def get_recipe_usages(
    session: Session, actor_user_id: str, item_id: str, branch_id: str | None
) -> list[dict[str, Any]]:
    started_at = perf_counter()
    scope_kind = "corporate" if branch_id is None else "branch"
    try:
        usages = _get_recipe_usages(session, actor_user_id, item_id, branch_id)
        _record_admin_catalog_metric(
            "admin_catalog.recipe_usages",
            result="success",
            started_at=started_at,
            scope_kind=scope_kind,
            usage_count=len(usages),
        )
        return usages
    except BusinessError as error:
        _record_admin_catalog_metric(
            "admin_catalog.recipe_usages",
            result=_admin_catalog_error_result(error),
            started_at=started_at,
            scope_kind=scope_kind,
            error_code=error.code,
        )
        raise
    except Exception:
        _record_admin_catalog_metric(
            "admin_catalog.recipe_usages",
            result="error",
            started_at=started_at,
            scope_kind=scope_kind,
            error_code="unexpected_error",
        )
        raise

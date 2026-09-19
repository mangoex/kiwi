"""Fixed, versioned combo compositions (PRD-FR-242).

This module intentionally keeps a combo as one sellable product.  Its component products are
operational snapshots only: their prices are never added to the order line.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _acquire_idempotency_lock,
    _actor_user_id,
    _audit,
    _now,
    actor_has_organization_authority,
    authorize_branch_scope,
    require_permission,
)

combo_compositions = models.product_compositions
combo_components = models.product_composition_components
combo_commands = models.product_composition_commands
combo_line_snapshots = models.order_line_component_snapshots
_MAX_NUMERIC_18_6 = Decimal("999999999999.999999")


def _key(value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise BusinessError("combo_idempotency_key_required", "Idempotency key is required")
    if len(normalized) > 180:
        raise BusinessError(
            "combo_idempotency_key_invalid", "Idempotency key exceeds 180 characters"
        )
    return normalized


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError(
            "combo_component_quantity_invalid", "Component quantity must be decimal"
        ) from exc
    if not result.is_finite() or result <= 0:
        raise BusinessError(
            "combo_component_quantity_invalid",
            "Component quantity must be a finite positive whole product unit",
        )
    # Check the exponent before formatting/quantizing.  Decimal("1e999999")
    # must be rejected deterministically rather than allocating its full fixed form.
    if result.adjusted() > 11:
        raise BusinessError(
            "combo_component_quantity_invalid", "Component quantity exceeds precision"
        )
    if result != result.to_integral_value():
        raise BusinessError(
            "combo_component_quantity_invalid",
            "Component quantity must be a finite positive whole product unit",
        )
    return result.quantize(Decimal("0.000001"))


def _persistable_quantity(value: Decimal) -> Decimal:
    """Keep expanded component quantities inside the Numeric(18,6) contract."""
    if not value.is_finite() or abs(value) > _MAX_NUMERIC_18_6:
        raise BusinessError(
            "combo_component_quantity_overflow",
            "Expanded combo component quantity exceeds persistence precision",
        )
    return value


def _composition_result(session: Session, composition: dict[str, Any]) -> dict[str, Any]:
    components = [
        dict(row)
        for row in session.execute(
            sa.select(
                combo_components.c.product_id,
                combo_components.c.quantity,
                combo_components.c.sort_order,
            )
            .where(combo_components.c.composition_id == composition["id"])
            .order_by(combo_components.c.sort_order)
        ).mappings()
    ]
    price = (
        session.execute(
            sa.select(models.price_versions.c.price_cents, models.price_versions.c.currency)
            .where(
                models.price_versions.c.product_id == composition["combo_product_id"],
                models.price_versions.c.organization_id == composition["organization_id"],
                models.price_versions.c.valid_to.is_(None),
            )
            .order_by(models.price_versions.c.valid_from.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not price:
        raise BusinessError("combo_price_required", "Combo requires a current canonical price")
    return {
        "id": str(composition["id"]),
        "combo_product_id": str(composition["combo_product_id"]),
        "branch_id": composition["branch_id"],
        "version": int(composition["version"]),
        "price_cents": int(price["price_cents"]),
        "currency": str(price["currency"]),
        "components": [
            {
                "product_id": str(row["product_id"]),
                "quantity": Decimal(str(row["quantity"])),
                "sort_order": int(row["sort_order"]),
            }
            for row in components
        ],
    }


def _scope_product(session: Session, product_id: str, branch_id: str | None) -> dict[str, Any]:
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
    if not product or (
        product["catalog_scope"] == "branch" and product["source_branch_id"] != branch_id
    ):
        raise BusinessError(
            "combo_component_out_of_scope", "Combo product is not active in this scope"
        )
    return dict(product)


def _require_writer(session: Session, actor_user_id: str, branch_id: str | None) -> str:
    actor = _actor_user_id(actor_user_id)
    if branch_id is None:
        if not actor_has_organization_authority(session, actor):
            raise AuthorizationError(
                "combo_corporate_scope_required", "Corporate authority is required"
            )
        require_permission(session, actor, "recipes.manage", None)
    else:
        authorize_branch_scope(session, actor, "recipes.manage", branch_id)
    return actor


def effective_composition(
    session: Session, combo_product_id: str, branch_id: str
) -> dict[str, Any] | None:
    composition = (
        session.execute(
            sa.select(combo_compositions)
            .where(
                combo_compositions.c.organization_id == ORGANIZATION_ID,
                combo_compositions.c.combo_product_id == combo_product_id,
                combo_compositions.c.status == "active",
                sa.or_(
                    combo_compositions.c.branch_id == branch_id,
                    combo_compositions.c.branch_id.is_(None),
                ),
            )
            .order_by(
                combo_compositions.c.branch_id.is_not(None).desc(),
                combo_compositions.c.version.desc(),
            )
            .limit(1)
        )
        .mappings()
        .first()
    )
    return _composition_result(session, dict(composition)) if composition else None


def _read_scope_composition(
    session: Session, combo_product_id: str, branch_id: str | None
) -> dict[str, Any] | None:
    scope = (
        combo_compositions.c.branch_id.is_(None)
        if branch_id is None
        else combo_compositions.c.branch_id == branch_id
    )
    row = (
        session.execute(
            sa.select(combo_compositions)
            .where(
                combo_compositions.c.organization_id == ORGANIZATION_ID,
                combo_compositions.c.combo_product_id == combo_product_id,
                combo_compositions.c.status == "active",
                scope,
            )
            .order_by(combo_compositions.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    return _composition_result(session, dict(row)) if row else None


def _readable_composition(
    session: Session, composition: dict[str, Any] | None
) -> dict[str, Any] | None:
    if composition is None:
        return None
    component_ids = [component["product_id"] for component in composition["components"]]
    products = {
        str(row["id"]): dict(row)
        for row in session.execute(
            sa.select(models.products.c.id, models.products.c.name, models.products.c.sku).where(
                models.products.c.id.in_(component_ids)
            )
        ).mappings()
    }
    return {
        **composition,
        "components": [
            {
                **component,
                "quantity": str(component["quantity"]),
                "name": products[component["product_id"]]["name"],
                "sku": products[component["product_id"]]["sku"],
            }
            for component in composition["components"]
        ],
    }


def composition_command_view(session: Session, result: dict[str, Any]) -> dict[str, Any]:
    """Render the immutable result stored for a composition command.

    A replay can refer to an older, superseded composition, so it must not be
    reconstructed from the current scope/version.  Product labels remain safe
    to read by ID because the historical composition holds the product FK.
    """
    return _readable_composition(session, result) or result


def get_composition_view(
    session: Session, actor_user_id: str, combo_product_id: str, branch_id: str | None
) -> dict[str, Any]:
    _require_writer(session, actor_user_id, branch_id)
    product = _scope_product(session, combo_product_id, branch_id)
    current = _read_scope_composition(session, combo_product_id, branch_id)
    effective = (
        effective_composition(session, combo_product_id, branch_id) if branch_id else current
    )
    return {
        "product": {
            "id": str(product["id"]),
            "name": str(product["name"]),
            "sku": str(product["sku"]),
            "catalog_scope": str(product["catalog_scope"]),
            "source_branch_id": product["source_branch_id"],
            "is_combo": effective is not None,
        },
        "branch_id": branch_id,
        "expected_version": int(current["version"]) if current else 0,
        "current_composition": _readable_composition(session, current),
        "effective_composition": _readable_composition(session, effective),
    }


def save_composition(
    session: Session,
    actor_user_id: str,
    combo_product_id: str,
    branch_id: str | None,
    *,
    expected_version: int,
    idempotency_key: str,
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    actor = _require_writer(session, actor_user_id, branch_id)
    if expected_version < 0 or not isinstance(components, list) or not components:
        raise BusinessError(
            "combo_composition_invalid", "Expected version and components are required"
        )
    # Canonicalize only request-owned scalar data before looking at catalog
    # state.  A recorded command must still replay after a component is
    # archived or itself later becomes a combo.
    normalized: list[tuple[str, Decimal]] = []
    for raw in components:
        if not isinstance(raw, dict):
            raise BusinessError("combo_composition_invalid", "Components must be objects")
        component_id = str(raw.get("product_id", ""))
        normalized.append((component_id, _decimal(raw.get("quantity"))))
    key = _key(idempotency_key)
    request = {
        "combo_product_id": combo_product_id,
        "branch_id": branch_id,
        "expected_version": expected_version,
        "components": [(item, str(quantity)) for item, quantity in normalized],
    }
    digest = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    # Command identity is organization-wide.  Serialize on the key *before*
    # inspecting its replay record; locking only the target product lets two
    # distinct products race into the global unique constraint.
    _acquire_idempotency_lock(session, "combo-composition-command", key)
    existing = (
        session.execute(
            sa.select(combo_commands).where(
                combo_commands.c.organization_id == ORGANIZATION_ID,
                combo_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if existing["actor_user_id"] != actor or existing["request_hash"] != digest:
            raise BusinessError("combo_idempotency_conflict", "Idempotency key payload differs")
        return dict(existing["result"])
    _acquire_idempotency_lock(
        session, "combo-composition", f"{combo_product_id}:{branch_id or 'corporate'}"
    )
    # Re-read after both locks.  This makes a same-key concurrent replay return
    # its canonical result instead of spuriously failing on the unique command row.
    existing = (
        session.execute(
            sa.select(combo_commands).where(
                combo_commands.c.organization_id == ORGANIZATION_ID,
                combo_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if existing["actor_user_id"] != actor or existing["request_hash"] != digest:
            raise BusinessError("combo_idempotency_conflict", "Idempotency key payload differs")
        return dict(existing["result"])
    combo = _scope_product(session, combo_product_id, branch_id)
    seen: set[str] = set()
    for component_id, _quantity_value in normalized:
        if not component_id or component_id in seen:
            raise BusinessError("combo_component_duplicate", "Combo components cannot repeat")
        if component_id == combo_product_id:
            raise BusinessError("combo_component_nested", "Combo cannot contain itself")
        _scope_product(session, component_id, branch_id)
        nested = (
            effective_composition(session, component_id, branch_id)
            if branch_id is not None
            else _read_scope_composition(session, component_id, None)
        )
        if nested:
            raise BusinessError("combo_component_nested", "Nested combos are not supported")
        seen.add(component_id)
    current = (
        session.execute(
            sa.select(combo_compositions)
            .where(
                combo_compositions.c.organization_id == ORGANIZATION_ID,
                combo_compositions.c.combo_product_id == combo_product_id,
                combo_compositions.c.branch_id.is_(None)
                if branch_id is None
                else combo_compositions.c.branch_id == branch_id,
                combo_compositions.c.status == "active",
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    current_version = int(current["version"]) if current else 0
    if current_version != expected_version:
        raise BusinessError("combo_composition_version_conflict", "Combo composition changed")
    now = _now()
    composition_id = str(uuid4())
    try:
        if current:
            session.execute(
                sa.update(combo_compositions)
                .where(combo_compositions.c.id == current["id"])
                .values(status="superseded", valid_to=now)
            )
        session.execute(
            combo_compositions.insert().values(
                id=composition_id,
                organization_id=ORGANIZATION_ID,
                combo_product_id=combo["id"],
                branch_id=branch_id,
                version=current_version + 1,
                status="active",
                valid_from=now,
                valid_to=None,
                created_by=actor,
                created_at=now,
            )
        )
        for index, (component_id, quantity) in enumerate(normalized, start=1):
            session.execute(
                combo_components.insert().values(
                    composition_id=composition_id,
                    product_id=component_id,
                    quantity=quantity,
                    sort_order=index,
                )
            )
        result = _composition_result(
            session,
            {
                "id": composition_id,
                "organization_id": ORGANIZATION_ID,
                "combo_product_id": combo_product_id,
                "branch_id": branch_id,
                "version": current_version + 1,
            },
        )
        result_json = {
            **result,
            "components": [
                {**component, "quantity": str(component["quantity"])}
                for component in result["components"]
            ],
        }
        session.execute(
            combo_commands.insert().values(
                id=str(uuid4()),
                organization_id=ORGANIZATION_ID,
                actor_user_id=actor,
                idempotency_key=key,
                request_hash=digest,
                result=result_json,
                created_at=now,
            )
        )
        _audit(
            session,
            "combo_composition.versioned",
            "product_composition",
            composition_id,
            {
                "combo_product_id": combo_product_id,
                "version": current_version + 1,
                "component_count": len(normalized),
            },
            branch_id=branch_id,
            actor_user_id=actor,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessError(
            "combo_composition_version_conflict", "Combo composition changed"
        ) from exc
    return result_json


def capture_combo_line(
    session: Session,
    *,
    order: dict[str, Any],
    line: dict[str, Any],
    created_at: Any,
    source_type: str = "order_acceptance",
    source_id: str | None = None,
    reservation_reason: str | None = None,
) -> bool:
    """Freeze a combo at acceptance and make its component tasks/reservation exactly once.

    The parent order-line snapshot remains the compatibility record consumed by existing
    amendment/cancellation compensation code. Component rows retain the complete interpretation.
    """
    composition = effective_composition(session, str(line["product_id"]), str(order["branch_id"]))
    if composition is None:
        return False
    existing = session.execute(
        sa.select(combo_line_snapshots.c.id)
        .where(combo_line_snapshots.c.order_line_id == line["id"])
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        return True
    # Delayed imports avoid a module cycle: operations invokes this after it has fully loaded.
    from restaurant_os.operations import (
        _active_recipe_components,
        _branch_warehouse_id,
        _cost,
        _id,
        _quantity,
        _record_calculated_consumption_movements,
        _sanitize_for_json,
    )

    # Validate the entire fixed offer before emitting any snapshot, task, or
    # reservation. A fixed combo has no syntax for per-component selections.
    line_quantity = Decimal(str(line["quantity"]))
    for component in composition["components"]:
        # The composition is historical configuration, not a bypass for the
        # product's current organization, active status, or branch scope.
        product = _scope_product(session, str(component["product_id"]), str(order["branch_id"]))
        if effective_composition(session, str(product["id"]), str(order["branch_id"])):
            raise BusinessError(
                "combo_component_nested",
                "Fixed combo component became a combo and cannot be expanded recursively",
            )
        availability = session.execute(
            sa.select(models.branch_product_availability.c.is_available).where(
                models.branch_product_availability.c.branch_id == order["branch_id"],
                models.branch_product_availability.c.product_id == product["id"],
            )
        ).scalar_one_or_none()
        if availability is False:
            raise BusinessError("combo_component_unavailable", "Combo component is unavailable")
        required_modifier = session.execute(
            sa.select(models.modifier_groups.c.id)
            .where(
                models.modifier_groups.c.product_id == product["id"],
                models.modifier_groups.c.status == "active",
                models.modifier_groups.c.is_required.is_(True),
            )
            .limit(1)
        ).scalar_one_or_none()
        if required_modifier:
            raise BusinessError(
                "combo_component_selection_required",
                "Fixed combo cannot represent a required component selection",
            )
        total_component_quantity = line_quantity * Decimal(str(component["quantity"]))
        _persistable_quantity(total_component_quantity)
        if total_component_quantity != total_component_quantity.to_integral_value():
            raise BusinessError(
                "combo_task_quantity_not_representable",
                "Fixed combo component quantity cannot be represented by the task contract",
            )
        if not _active_recipe_components(session, str(product["id"]), str(order["branch_id"])):
            raise BusinessError(
                "combo_component_recipe_required",
                "Every combo component requires an active recipe",
            )

    aggregate: dict[str, dict[str, Any]] = {}
    first_recipe: dict[str, Any] | None = None
    total_cost = Decimal("0")
    warehouse_id = _branch_warehouse_id(session, str(order["branch_id"]))
    for component in composition["components"]:
        product = _scope_product(session, str(component["product_id"]), str(order["branch_id"]))
        multiplier = line_quantity * Decimal(str(component["quantity"]))
        _persistable_quantity(multiplier)
        recipe = _active_recipe_components(session, str(product["id"]), str(order["branch_id"]))
        if not recipe:
            raise BusinessError(
                "combo_component_recipe_required", "Every combo component requires an active recipe"
            )
        if first_recipe is None:
            first_recipe = recipe[0]
        component_breakdown: list[dict[str, Any]] = []
        for item in recipe:
            gross = _quantity(
                Decimal(str(item["gross_quantity"]))
                / Decimal(str(item["yield_quantity"]))
                * multiplier
            )
            _persistable_quantity(gross)
            net = _quantity(
                Decimal(str(item["net_quantity"]))
                / Decimal(str(item["yield_quantity"]))
                * multiplier
            )
            _persistable_quantity(net)
            state = session.execute(
                sa.select(models.inventory_cost_states.c.average_unit_cost).where(
                    models.inventory_cost_states.c.branch_id == order["branch_id"],
                    models.inventory_cost_states.c.warehouse_id == warehouse_id,
                    models.inventory_cost_states.c.item_id == item["item_id"],
                )
            ).scalar_one_or_none()
            unit_cost = _cost(state or 0)
            item_cost = _cost(gross * unit_cost)
            row = {
                "item_id": item["item_id"],
                "item_name": item["item_name"],
                "unit_id": item["unit_id"],
                "unit_code": item["unit_code"],
                "net_quantity": net,
                "gross_quantity": gross,
                "waste_rate": item["waste_rate"],
                "unit_cost": unit_cost,
                "total_cost": item_cost,
            }
            component_breakdown.append(_sanitize_for_json(row))
            previous = aggregate.get(str(item["item_id"]))
            if previous:
                previous["net_quantity"] = _quantity(Decimal(str(previous["net_quantity"])) + net)
                previous["gross_quantity"] = _quantity(
                    Decimal(str(previous["gross_quantity"])) + gross
                )
                previous["total_cost"] = _cost(Decimal(str(previous["total_cost"])) + item_cost)
            else:
                aggregate[str(item["item_id"])] = row
            total_cost += item_cost
        task_id = _id()
        # The snapshot carries a non-null FK to this exact KDS task.  Create
        # the task first so PostgreSQL enforces the association immediately.
        session.execute(
            models.production_tasks.insert().values(
                id=task_id,
                organization_id=order["organization_id"],
                branch_id=order["branch_id"],
                order_id=order["id"],
                order_line_id=line["id"],
                station=product["station"],
                status="PENDING",
                product_name=product["name"],
                quantity=int(multiplier),
                created_at=created_at,
                started_at=None,
                completed_at=None,
            )
        )
        session.execute(
            combo_line_snapshots.insert().values(
                id=str(uuid4()),
                order_line_id=line["id"],
                production_task_id=task_id,
                composition_id=composition["id"],
                composition_version=composition["version"],
                component_product_id=product["id"],
                component_product_name=product["name"],
                component_quantity=multiplier,
                station=product["station"],
                recipe_id=recipe[0]["recipe_id"],
                recipe_version=recipe[0]["recipe_version"],
                recipe_components=component_breakdown,
                created_at=created_at,
            )
        )
    if first_recipe is None:  # defensive; an empty composition is rejected by the writer.
        raise BusinessError("combo_composition_invalid", "Combo composition has no components")
    breakdown = [_sanitize_for_json(value) for value in aggregate.values()]
    session.execute(
        models.order_line_consumption_snapshots.insert().values(
            order_line_id=line["id"],
            order_id=order["id"],
            recipe_id=first_recipe["recipe_id"],
            recipe_version=first_recipe["recipe_version"],
            branch_id=order["branch_id"],
            components=breakdown,
            modifiers=[],
            total_theoretical_cost=total_cost,
            created_at=created_at,
        )
    )
    _record_calculated_consumption_movements(
        session,
        components=breakdown,
        product_name=line["product_name"],
        movement_type="SALE_RESERVATION",
        sign=-1,
        reason=reservation_reason or f"Reserva por aceptación de pedido {order['folio']}",
        source_type=source_type,
        source_id=source_id or str(order["id"]),
        created_at=created_at,
        branch_id=order["branch_id"],
    )
    return True


def record_combo_component_snapshot_movements(
    session: Session,
    *,
    order_line_id: str,
    component_product_id: str,
    product_name: str,
    movement_type: str,
    sign: int,
    reason: str,
    source_type: str,
    source_id: str,
    created_at: Any,
    branch_id: str,
    affected_line_quantity: Any,
    original_line_quantity: Any,
) -> list[dict[str, Any]] | None:
    """Record one component's frozen recipe movement for a corrected combo.

    A combo line's parent consumption snapshot is an aggregate compatibility
    record.  Mixed task dispositions instead settle each component snapshot,
    preserving distinct station outcomes without double-counting ingredients.
    """
    from restaurant_os.operations import (
        _cost,
        _quantity,
        _record_calculated_consumption_movements,
        _sanitize_for_json,
    )

    snapshot = (
        session.execute(
            sa.select(combo_line_snapshots).where(
                combo_line_snapshots.c.order_line_id == order_line_id,
                combo_line_snapshots.c.component_product_id == component_product_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None:
        return None
    try:
        affected = Decimal(str(affected_line_quantity))
        original = Decimal(str(original_line_quantity))
    except (InvalidOperation, ValueError) as exc:
        raise BusinessError(
            "combo_snapshot_quantity_invalid", "Combo correction quantity is invalid"
        ) from exc
    if (
        not affected.is_finite()
        or not original.is_finite()
        or affected <= 0
        or original <= 0
        or affected > original
    ):
        raise BusinessError(
            "combo_snapshot_quantity_invalid",
            "Combo correction quantity must be positive and no greater than the original line",
        )
    factor = affected / original
    components: list[dict[str, Any]] = []
    for raw in snapshot["recipe_components"]:
        component = dict(raw)
        component["net_quantity"] = _quantity(Decimal(str(component["net_quantity"])) * factor)
        component["gross_quantity"] = _quantity(Decimal(str(component["gross_quantity"])) * factor)
        component["unit_cost"] = _cost(component.get("unit_cost", 0))
        component["total_cost"] = _cost(Decimal(str(component.get("total_cost", 0))) * factor)
        components.append(_sanitize_for_json(component))
    return _record_calculated_consumption_movements(
        session,
        components=components,
        product_name=product_name,
        movement_type=movement_type,
        sign=sign,
        reason=reason,
        source_type=source_type,
        source_id=source_id,
        created_at=created_at,
        branch_id=branch_id,
    )


def restore_combo_line_from_snapshot(
    session: Session,
    *,
    order: dict[str, Any],
    source_line: dict[str, Any],
    replacement_line: dict[str, Any],
    created_at: Any,
) -> bool:
    """Recreate a corrected combo only from its immutable accepted snapshots.

    Reopen/correction paths must never expand today's composition or recipe.  The
    caller owns cancellation and compensation of source tasks.  A correction
    that already releases only the reduced quantity keeps the remaining
    reservation in place, so it recreates snapshots/tasks without reserving a
    second time.
    """
    from restaurant_os.operations import (
        _cost,
        _id,
        _quantity,
        _sanitize_for_json,
    )

    components = [
        dict(row)
        for row in session.execute(
            sa.select(combo_line_snapshots)
            .where(combo_line_snapshots.c.order_line_id == source_line["id"])
            .order_by(combo_line_snapshots.c.id)
        ).mappings()
    ]
    if not components:
        return False
    source_snapshot = (
        session.execute(
            sa.select(models.order_line_consumption_snapshots).where(
                models.order_line_consumption_snapshots.c.order_line_id == source_line["id"]
            )
        )
        .mappings()
        .one_or_none()
    )
    if source_snapshot is None:
        raise BusinessError(
            "combo_snapshot_missing",
            "Combo component snapshots require their aggregate consumption snapshot",
        )
    source_quantity = Decimal(str(source_line["quantity"]))
    replacement_quantity = Decimal(str(replacement_line["quantity"]))
    if (
        source_quantity <= 0
        or replacement_quantity <= 0
        or source_quantity != source_quantity.to_integral_value()
        or replacement_quantity != replacement_quantity.to_integral_value()
    ):
        raise BusinessError(
            "combo_snapshot_quantity_invalid", "Combo line quantities must be positive"
        )
    factor = replacement_quantity / source_quantity

    def scaled_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            row["net_quantity"] = _quantity(Decimal(str(row["net_quantity"])) * factor)
            row["gross_quantity"] = _quantity(Decimal(str(row["gross_quantity"])) * factor)
            row["unit_cost"] = _cost(row.get("unit_cost", 0))
            row["total_cost"] = _cost(Decimal(str(row.get("total_cost", 0))) * factor)
            result.append(_sanitize_for_json(row))
        return result

    # Validate every frozen component before any replacement writes.
    prepared: list[tuple[dict[str, Any], Decimal, list[dict[str, Any]]]] = []
    for component in components:
        quantity = Decimal(str(component["component_quantity"])) * factor
        if quantity <= 0 or quantity != quantity.to_integral_value():
            raise BusinessError(
                "combo_task_quantity_not_representable",
                "Frozen combo component quantity cannot be represented by the task contract",
            )
        prepared.append(
            (component, quantity, scaled_breakdown(list(component["recipe_components"])))
        )
    aggregate = scaled_breakdown(list(source_snapshot["components"]))

    for component, quantity, recipe_components in prepared:
        task_id = _id()
        session.execute(
            models.production_tasks.insert().values(
                id=task_id,
                organization_id=order["organization_id"],
                branch_id=order["branch_id"],
                order_id=order["id"],
                order_line_id=replacement_line["id"],
                station=component["station"],
                status="PENDING",
                product_name=component["component_product_name"],
                quantity=int(quantity),
                created_at=created_at,
                started_at=None,
                completed_at=None,
            )
        )
        session.execute(
            combo_line_snapshots.insert().values(
                id=str(uuid4()),
                order_line_id=replacement_line["id"],
                production_task_id=task_id,
                composition_id=component["composition_id"],
                composition_version=component["composition_version"],
                component_product_id=component["component_product_id"],
                component_product_name=component["component_product_name"],
                component_quantity=quantity,
                station=component["station"],
                recipe_id=component["recipe_id"],
                recipe_version=component["recipe_version"],
                recipe_components=recipe_components,
                created_at=created_at,
            )
        )
    total_cost = sum((_cost(component["total_cost"]) for component in aggregate), Decimal("0"))
    session.execute(
        models.order_line_consumption_snapshots.insert().values(
            order_line_id=replacement_line["id"],
            order_id=order["id"],
            recipe_id=source_snapshot["recipe_id"],
            recipe_version=source_snapshot["recipe_version"],
            branch_id=order["branch_id"],
            components=aggregate,
            modifiers=[],
            total_theoretical_cost=_cost(total_cost),
            created_at=created_at,
        )
    )
    return True

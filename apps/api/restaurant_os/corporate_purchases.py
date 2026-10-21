"""Authoritative corporate purchase orders and distributed receipts."""

from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, TypeVar, cast

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _acquire_idempotency_lock,
    _acquire_inventory_advisory_locks,
    _actor_has_organization_scope,
    _actor_user_id,
    _audit,
    _cost,
    _id,
    _money,
    _now,
    _parse_document_date,
    _physical_inventory_quantity,
    _quantity,
    _record_authorization_denied,
    _sanitize_for_json,
    require_permission,
)
from restaurant_os.presentation_rules import presentation_values
from restaurant_os.purchase_allocation import apportion
from restaurant_os.purchase_workspace import (
    MAX_LINES,
    bounded_payload,
    purchase_decimal,
    purchase_line_values,
)

ORDER_KEYS = {
    "legal_entity_id",
    "supplier_id",
    "folio",
    "order_date",
    "currency",
    "notes",
    "lines",
}
LINE_KEYS = {"presentation_id", "quantity", "unit_price", "discount", "tax", "allocations"}
ALLOCATION_KEYS = {"branch_id", "warehouse_id", "quantity"}
RECEIPT_KEYS = {"expected_version", "branch_id", "warehouse_id", "received_at", "lines"}
RECEIPT_LINE_KEYS = {"allocation_id", "quantity"}

logger = logging.getLogger(__name__)
CorporateResult = TypeVar("CorporateResult")


def _record_corporate_purchase_metric(
    operation: str,
    result: str,
    *,
    order_id: str | None = None,
    error_code: str | None = None,
) -> None:
    """Emit bounded operational metadata without payloads, notes, prices, or keys."""
    extra: dict[str, Any] = {
        "metric": "corporate_purchase_command",
        "operation": operation,
        "result": result,
    }
    if order_id:
        extra["order_id"] = order_id
    if error_code:
        extra["error_code"] = error_code
    logger.info("corporate_purchase_command", extra=extra)


def _observe_corporate_mutation(
    operation: str,
) -> Callable[[Callable[..., CorporateResult]], Callable[..., CorporateResult]]:
    """Observe rejected mutations while leaving transaction ownership unchanged."""

    def decorate(
        command: Callable[..., CorporateResult],
    ) -> Callable[..., CorporateResult]:
        @wraps(command)
        def observed(*args: Any, **kwargs: Any) -> CorporateResult:
            order_id = None if operation == "create" else str(args[1]) if len(args) > 1 else None
            try:
                return command(*args, **kwargs)
            except (AuthorizationError, BusinessError) as exc:
                _record_corporate_purchase_metric(
                    operation,
                    "rejected",
                    order_id=order_id,
                    error_code=exc.code,
                )
                raise

        return observed

    return decorate


def _require_corporate_permission(session: Session, actor_id: str, permission: str) -> None:
    actor = _actor_user_id(actor_id)
    if not _actor_has_organization_scope(session, actor, permission):
        _record_authorization_denied(
            session,
            actor_user_id=actor or None,
            permission_code=permission,
            branch_id=None,
            reason="organization_scope_required",
        )
        raise AuthorizationError(
            "permission_denied", "Corporate purchases require organization scope"
        )
    require_permission(session, actor, permission, None)


def _command_hash(command_type: str, payload: dict[str, Any]) -> str:
    body = json.dumps(
        {"command_type": command_type, "payload": _sanitize_for_json(payload)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


def _require_exact_storage(session: Session, values: Any) -> None:
    """Reject loss through SQLite's Numeric codec; business arithmetic stays Decimal."""
    dialect = session.get_bind().dialect
    if dialect.name != "sqlite":
        return
    if isinstance(values, dict):
        for value in values.values():
            _require_exact_storage(session, value)
    elif isinstance(values, list):
        for value in values:
            _require_exact_storage(session, value)
    elif isinstance(values, Decimal):
        numeric = sa.Numeric(18, 6)
        # SQLAlchemy exposes these dialect codec hooks without type annotations.
        bind_hook = cast(
            Callable[[sa.engine.Dialect], Callable[[Decimal], Any] | None],
            numeric.bind_processor,
        )
        result_hook = cast(
            Callable[[sa.engine.Dialect, Any], Callable[[Any], Decimal] | None],
            numeric.result_processor,
        )
        bind = bind_hook(dialect)
        result = result_hook(dialect, None)
        encoded = bind(values) if bind else values
        decoded = result(encoded) if result else encoded
        if decoded != values:
            raise BusinessError(
                "corporate_purchase_storage_precision_unsupported",
                "Amount cannot be stored exactly by this SQLite runtime",
            )


def _command_replay(
    session: Session,
    actor_id: str,
    command_type: str,
    key: str,
    request_hash: str,
) -> dict[str, Any] | None:
    normalized_key = key.strip()
    if not normalized_key or len(normalized_key) > 180:
        raise BusinessError("idempotency_key_required", "Idempotency key is required")
    _acquire_idempotency_lock(session, "corporate-purchase", normalized_key)
    command = (
        session.execute(
            sa.select(models.corporate_purchase_commands).where(
                models.corporate_purchase_commands.c.organization_id == ORGANIZATION_ID,
                models.corporate_purchase_commands.c.idempotency_key == normalized_key,
            )
        )
        .mappings()
        .first()
    )
    if not command:
        return None
    if (
        command["actor_user_id"] != actor_id
        or command["command_type"] != command_type
        or command["request_hash"] != request_hash
    ):
        raise BusinessError(
            "corporate_purchase_idempotency_conflict",
            "Idempotency key was already used for another corporate purchase command",
        )
    _record_corporate_purchase_metric(
        command_type,
        "replay",
        order_id=str(command["order_id"]) if command["order_id"] else None,
    )
    return dict(command["result"])


def _store_command(
    session: Session,
    actor_id: str,
    command_type: str,
    key: str,
    request_hash: str,
    order_id: str | None,
    result: dict[str, Any],
) -> None:
    session.execute(
        models.corporate_purchase_commands.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            actor_user_id=actor_id,
            command_type=command_type,
            idempotency_key=key.strip(),
            request_hash=request_hash,
            order_id=order_id,
            result=_sanitize_for_json(result),
            created_at=_now(),
        )
    )


def _serialize_order(session: Session, order_id: str) -> dict[str, Any]:
    order = (
        session.execute(
            sa.select(models.corporate_purchase_orders).where(
                models.corporate_purchase_orders.c.id == order_id,
                models.corporate_purchase_orders.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not order:
        raise BusinessError("corporate_purchase_not_found", "Corporate purchase was not found")
    lines = []
    for line in session.execute(
        sa.select(models.corporate_purchase_order_lines)
        .where(models.corporate_purchase_order_lines.c.order_id == order_id)
        .order_by(
            models.corporate_purchase_order_lines.c.created_at,
            models.corporate_purchase_order_lines.c.id,
        )
    ).mappings():
        allocations: list[dict[str, Any]] = []
        for row in session.execute(
            sa.select(models.corporate_purchase_allocations)
            .where(models.corporate_purchase_allocations.c.order_line_id == line["id"])
            .order_by(models.corporate_purchase_allocations.c.branch_id)
        ).mappings():
            allocation = dict(row)
            allocation["quantity"] = allocation["presentation_quantity"]
            allocation["received_quantity"] = allocation["received_presentation_quantity"]
            allocation["pending_quantity"] = _quantity(
                Decimal(str(allocation["presentation_quantity"]))
                - Decimal(str(allocation["received_presentation_quantity"]))
            )
            allocations.append(allocation)
        lines.append(
            {
                **dict(line),
                "quantity": line["presentation_quantity"],
                "allocations": allocations,
            }
        )
    receipts = []
    for receipt in session.execute(
        sa.select(models.corporate_purchase_receipts)
        .where(models.corporate_purchase_receipts.c.order_id == order_id)
        .order_by(models.corporate_purchase_receipts.c.created_at)
    ).mappings():
        receipt_lines = [
            dict(row)
            for row in session.execute(
                sa.select(models.corporate_purchase_receipt_lines).where(
                    models.corporate_purchase_receipt_lines.c.receipt_id == receipt["id"]
                )
            ).mappings()
        ]
        receipts.append({**dict(receipt), "lines": receipt_lines})
    return cast(
        dict[str, Any],
        _sanitize_for_json({**dict(order), "lines": lines, "receipts": receipts}),
    )


def list_corporate_purchase_orders(
    session: Session,
    actor_user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.read")
    if (
        isinstance(limit, bool)
        or isinstance(offset, bool)
        or not 1 <= limit <= 100
        or not 0 <= offset <= 10_000
    ):
        raise BusinessError(
            "corporate_purchase_pagination_invalid",
            "Pagination must use limit 1..100 and offset 0..10000",
        )
    rows = session.execute(
        sa.select(models.corporate_purchase_orders)
        .where(models.corporate_purchase_orders.c.organization_id == ORGANIZATION_ID)
        .order_by(
            models.corporate_purchase_orders.c.updated_at.desc(),
            models.corporate_purchase_orders.c.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).mappings()
    return [cast(dict[str, Any], _sanitize_for_json(dict(row))) for row in rows]


def get_corporate_purchase_order(
    session: Session, order_id: str, actor_user_id: str
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.read")
    return _serialize_order(session, order_id)


def corporate_purchase_options(session: Session, actor_user_id: str) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.read")
    legal_entities = [
        dict(row)
        for row in session.execute(
            sa.select(models.legal_entities)
            .where(
                models.legal_entities.c.organization_id == ORGANIZATION_ID,
                models.legal_entities.c.status == "active",
            )
            .order_by(models.legal_entities.c.name)
        ).mappings()
    ]
    destinations = [
        dict(row)
        for row in session.execute(
            sa.select(
                models.branches.c.id.label("branch_id"),
                models.branches.c.name.label("branch_name"),
                models.branches.c.legal_entity_id,
                models.warehouses.c.id.label("warehouse_id"),
                models.warehouses.c.name.label("warehouse_name"),
            )
            .select_from(
                models.branches.join(
                    models.warehouses, models.warehouses.c.branch_id == models.branches.c.id
                )
            )
            .where(
                models.branches.c.organization_id == ORGANIZATION_ID,
                models.branches.c.status == "active",
                models.warehouses.c.organization_id == ORGANIZATION_ID,
                models.warehouses.c.status == "active",
            )
            .order_by(models.branches.c.name)
        ).mappings()
    ]
    suppliers = [
        dict(row)
        for row in session.execute(
            sa.select(models.suppliers.c.id, models.suppliers.c.commercial_name)
            .where(
                models.suppliers.c.organization_id == ORGANIZATION_ID,
                models.suppliers.c.status == "active",
            )
            .order_by(models.suppliers.c.commercial_name)
        ).mappings()
    ]
    presentations = [
        dict(row)
        for row in session.execute(
            sa.select(
                models.purchase_presentations.c.id,
                models.purchase_presentations.c.supplier_id,
                models.purchase_presentations.c.name,
                models.purchase_presentations.c.last_net_price,
                models.inventory_items.c.name.label("item_name"),
                models.inventory_items.c.sku.label("item_sku"),
            )
            .select_from(
                models.purchase_presentations.join(
                    models.suppliers,
                    models.suppliers.c.id == models.purchase_presentations.c.supplier_id,
                ).join(
                    models.inventory_items,
                    models.inventory_items.c.id == models.purchase_presentations.c.item_id,
                )
            )
            .where(
                models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
                models.purchase_presentations.c.status == "active",
                models.suppliers.c.organization_id == ORGANIZATION_ID,
                models.suppliers.c.status == "active",
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
            )
            .order_by(models.inventory_items.c.name, models.purchase_presentations.c.name)
        ).mappings()
    ]
    return cast(
        dict[str, Any],
        _sanitize_for_json(
            {
                "legal_entities": legal_entities,
                "destinations": destinations,
                "suppliers": suppliers,
                "presentations": presentations,
            }
        ),
    )


def _allocation_cost_target(session: Session, allocation: dict[str, Any]) -> Decimal:
    if allocation.get("inventory_cost_target") is not None:
        return Decimal(str(allocation["inventory_cost_target"]))
    rows = list(
        session.execute(
            sa.select(
                models.corporate_purchase_allocations.c.id,
                models.corporate_purchase_allocations.c.presentation_quantity,
            )
            .where(
                models.corporate_purchase_allocations.c.order_line_id
                == allocation["order_line_id"]
            )
            .order_by(
                models.corporate_purchase_allocations.c.created_at,
                models.corporate_purchase_allocations.c.id,
            )
        ).mappings()
    )
    remaining = _money(allocation["line_inventory_cost"])
    line_quantity = Decimal(str(allocation["line_presentation_quantity"]))
    for index, row in enumerate(rows):
        target = (
            remaining
            if index == len(rows) - 1
            else _money(
                Decimal(str(allocation["line_inventory_cost"]))
                * Decimal(str(row["presentation_quantity"]))
                / line_quantity
            )
        )
        if row["id"] == allocation["id"]:
            return target
        remaining = _money(remaining - target)
    raise BusinessError(
        "corporate_purchase_destination_invalid", "Allocation cost target was not found"
    )


def _validate_allocation_plan(session: Session, order: dict[str, Any]) -> None:
    """Refuse invalid historical plans without rewriting their snapshots or effects."""
    for line in session.execute(
        sa.select(models.corporate_purchase_order_lines).where(
            models.corporate_purchase_order_lines.c.order_id == order["id"]
        )
    ).mappings():
        allocations = list(session.execute(
            sa.select(models.corporate_purchase_allocations).where(
                models.corporate_purchase_allocations.c.order_line_id == line["id"]
            )
        ).mappings())
        valid = bool(allocations)
        for field in ("presentation_quantity", "base_quantity"):
            valid = valid and sum(
                (Decimal(str(row[field])) for row in allocations), Decimal("0")
            ) == Decimal(str(line[field]))
        targets = []
        for row in allocations:
            target = _allocation_cost_target(session, {
                **dict(row),
                "line_inventory_cost": line["inventory_cost"],
                "line_presentation_quantity": line["presentation_quantity"],
            })
            targets.append(target)
            valid = valid and target >= 0 and Decimal(str(row["base_quantity"])) > 0
            for field in ("presentation_quantity", "base_quantity"):
                received = Decimal(str(row[f"received_{field}"]))
                valid = valid and 0 <= received <= Decimal(str(row[field]))
        valid = valid and sum(targets, Decimal("0")) == Decimal(str(line["inventory_cost"]))
        if order["allocation_policy_version"] == 2:
            sequences = {row["allocation_sequence"] for row in allocations}
            valid = valid and sequences == set(range(len(allocations))) and all(
                row["inventory_cost_target"] is not None for row in allocations
            )
        if not valid:
            raise BusinessError(
                "corporate_purchase_legacy_allocation_invalid",
                "Allocation plan requires authorized reconciliation before effects",
            )


def _prepare_order(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    bounded_payload(payload, ORDER_KEYS)
    legal_entity_id = str(payload.get("legal_entity_id", "")).strip()
    supplier_id = str(payload.get("supplier_id", "")).strip()
    folio = str(payload.get("folio", "")).strip()
    currency = str(payload.get("currency", "MXN")).strip().upper()
    notes = payload.get("notes")
    if not folio or len(folio) > 80 or currency != "MXN":
        raise BusinessError("corporate_purchase_payload_invalid", "Invalid folio or currency")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 600):
        raise BusinessError("corporate_purchase_payload_invalid", "Invalid notes")
    if not session.scalar(
        sa.select(models.legal_entities.c.id).where(
            models.legal_entities.c.id == legal_entity_id,
            models.legal_entities.c.organization_id == ORGANIZATION_ID,
            models.legal_entities.c.status == "active",
        )
    ):
        raise BusinessError(
            "corporate_purchase_legal_entity_invalid", "Active legal entity is required"
        )
    if not session.scalar(
        sa.select(models.suppliers.c.id).where(
            models.suppliers.c.id == supplier_id,
            models.suppliers.c.organization_id == ORGANIZATION_ID,
            models.suppliers.c.status == "active",
        )
    ):
        raise BusinessError("corporate_purchase_supplier_invalid", "Active supplier is required")
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= MAX_LINES:
        raise BusinessError("corporate_purchase_lines_required", "Order requires 1 to 200 lines")
    try:
        order_date = _parse_document_date(payload.get("order_date"), _now())
    except (ValueError, TypeError, OverflowError) as exc:
        raise BusinessError("corporate_purchase_date_invalid", "Invalid order date") from exc

    prepared_lines = []
    subtotal = Decimal("0")
    discounts = Decimal("0")
    taxes = Decimal("0")
    for index, raw_line in enumerate(raw_lines):
        if not isinstance(raw_line, dict):
            raise BusinessError("corporate_purchase_line_invalid", f"Invalid line {index + 1}")
        bounded_payload(raw_line, LINE_KEYS)
        presentation = (
            session.execute(
                sa.select(models.purchase_presentations).where(
                    models.purchase_presentations.c.id == str(raw_line.get("presentation_id", "")),
                    models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
                    models.purchase_presentations.c.supplier_id == supplier_id,
                    models.purchase_presentations.c.status == "active",
                )
            )
            .mappings()
            .first()
        )
        if not presentation:
            raise BusinessError(
                "corporate_purchase_presentation_invalid", "Supplier presentation was not found"
            )
        presentation_values(session, dict(presentation), None)
        item = session.execute(sa.select(models.inventory_items).where(
            models.inventory_items.c.id == presentation["item_id"],
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
        )).mappings().one()
        unit_codes: dict[str, str] = {str(row[0]): str(row[1]) for row in session.execute(sa.select(
            models.inventory_units.c.id, models.inventory_units.c.code,
        ).where(models.inventory_units.c.id.in_(
            [presentation["base_unit_id"], presentation["commercial_unit_id"]]
        ))).all()}
        frozen_presentation = {
            **dict(presentation), "item_name": item["name"], "item_sku": item["sku"],
            "base_unit_code": unit_codes[presentation["base_unit_id"]],
            "commercial_unit_code": unit_codes[presentation["commercial_unit_id"]],
        }
        line = purchase_line_values(
            {
                key: raw_line.get(key)
                for key in ("presentation_id", "quantity", "unit_price", "discount", "tax")
            },
            frozen_presentation,
        )
        raw_allocations = raw_line.get("allocations")
        if not isinstance(raw_allocations, list) or not raw_allocations:
            raise BusinessError(
                "corporate_purchase_allocations_required", "Each line requires allocations"
            )
        allocations: list[dict[str, Any]] = []
        allocation_total = Decimal("0")
        seen_destinations: set[tuple[str, str]] = set()
        for raw_allocation in raw_allocations:
            if not isinstance(raw_allocation, dict):
                raise BusinessError("corporate_purchase_destination_invalid", "Invalid destination")
            bounded_payload(raw_allocation, ALLOCATION_KEYS)
            branch_id = str(raw_allocation.get("branch_id", ""))
            warehouse_id = str(raw_allocation.get("warehouse_id", ""))
            quantity = purchase_decimal(raw_allocation.get("quantity"), "quantity", positive=True)
            destination = session.execute(
                sa.select(models.branches.c.id)
                .select_from(
                    models.branches.join(
                        models.warehouses,
                        models.warehouses.c.branch_id == models.branches.c.id,
                    )
                )
                .where(
                    models.branches.c.id == branch_id,
                    models.branches.c.organization_id == ORGANIZATION_ID,
                    models.branches.c.legal_entity_id == legal_entity_id,
                    models.branches.c.status == "active",
                    models.warehouses.c.id == warehouse_id,
                    models.warehouses.c.organization_id == ORGANIZATION_ID,
                    models.warehouses.c.status == "active",
                )
            ).scalar_one_or_none()
            if not destination or (branch_id, warehouse_id) in seen_destinations:
                raise BusinessError(
                    "corporate_purchase_destination_invalid",
                    "Destination must be an active branch warehouse of the legal entity",
                )
            disabled = session.scalar(
                sa.select(models.supplier_branch_terms.c.is_enabled).where(
                    models.supplier_branch_terms.c.supplier_id == supplier_id,
                    models.supplier_branch_terms.c.branch_id == branch_id,
                )
            )
            if disabled is False:
                raise BusinessError(
                    "corporate_purchase_destination_invalid", "Supplier is disabled at destination"
                )
            presentation_values(session, dict(presentation), branch_id)
            seen_destinations.add((branch_id, warehouse_id))
            allocation_total += quantity
            allocations.append(
                {
                    "branch_id": branch_id,
                    "warehouse_id": warehouse_id,
                    "presentation_quantity": quantity,
                }
            )
        if allocation_total != line["presentation_quantity"]:
            raise BusinessError(
                "corporate_purchase_allocation_mismatch",
                "Allocated quantity must exactly match ordered quantity",
            )
        weights = [allocation["presentation_quantity"] for allocation in allocations]
        base_targets = apportion(line["base_quantity"], weights)
        cost_targets = apportion(line["inventory_cost"], weights)
        for sequence, allocation in enumerate(allocations):
            allocation["allocation_sequence"] = sequence
            allocation["base_quantity"] = purchase_decimal(
                base_targets[sequence], "base_quantity", positive=True
            )
            allocation["inventory_cost_target"] = cost_targets[sequence]
        prepared_lines.append({**line, "allocations": allocations})
        subtotal += line["inventory_cost"] + line["discount"]
        discounts += line["discount"]
        taxes += line["tax"]
    return {
        "legal_entity_id": legal_entity_id,
        "supplier_id": supplier_id,
        "folio": folio,
        "order_date": order_date,
        "currency": currency,
        "subtotal": purchase_decimal(subtotal, "subtotal"),
        "discount_total": purchase_decimal(discounts, "discount_total"),
        "tax_total": purchase_decimal(taxes, "tax_total"),
        "total": purchase_decimal(subtotal - discounts + taxes, "total"),
        "notes": notes,
        "lines": prepared_lines,
    }


@_observe_corporate_mutation("create")
def create_corporate_purchase_order(
    session: Session, payload: dict[str, Any], actor_user_id: str, idempotency_key: str
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.manage")
    request_hash = _command_hash("create", payload)
    replay = _command_replay(session, actor_id, "create", idempotency_key, request_hash)
    if replay is not None:
        return replay
    prepared = _prepare_order(session, payload)
    _require_exact_storage(session, prepared)
    now = _now()
    order_id = _id()
    try:
        session.execute(
            models.corporate_purchase_orders.insert().values(
                id=order_id,
                organization_id=ORGANIZATION_ID,
                legal_entity_id=prepared["legal_entity_id"],
                supplier_id=prepared["supplier_id"],
                folio=prepared["folio"],
                order_date=prepared["order_date"],
                currency=prepared["currency"],
                subtotal=prepared["subtotal"],
                discount_total=prepared["discount_total"],
                tax_total=prepared["tax_total"],
                total=prepared["total"],
                status="DRAFT",
                version=1,
                allocation_policy_version=2,
                notes=prepared["notes"],
                created_by=actor_id,
                approved_by=None,
                cancelled_by=None,
                cancellation_reason=None,
                created_at=now,
                approved_at=None,
                cancelled_at=None,
                updated_at=now,
            )
        )
        for line_values in prepared["lines"]:
            line_id = _id()
            allocations = line_values["allocations"]
            session.execute(
                models.corporate_purchase_order_lines.insert().values(
                    id=line_id,
                    order_id=order_id,
                    **{key: value for key, value in line_values.items() if key != "allocations"},
                    created_at=now,
                )
            )
            session.execute(
                models.corporate_purchase_allocations.insert(),
                [
                    {
                        "id": _id(),
                        "order_line_id": line_id,
                        **allocation,
                        "received_presentation_quantity": Decimal("0"),
                        "received_base_quantity": Decimal("0"),
                        "created_at": now,
                        "updated_at": now,
                    }
                    for allocation in allocations
                ],
            )
    except IntegrityError as exc:
        raise BusinessError(
            "corporate_purchase_identity_conflict", "Corporate purchase folio already exists"
        ) from exc
    _audit(
        session,
        "corporate_purchase.created",
        "corporate_purchase_order",
        order_id,
        {
            "status": "DRAFT",
            "version": 1,
            "legal_entity_id": prepared["legal_entity_id"],
            "supplier_id": prepared["supplier_id"],
            "line_count": len(prepared["lines"]),
            "allocation_count": sum(
                len(line["allocations"]) for line in prepared["lines"]
            ),
            "destination_count": len(
                {
                    (allocation["branch_id"], allocation["warehouse_id"])
                    for line in prepared["lines"]
                    for allocation in line["allocations"]
                }
            ),
        },
        branch_id=None,
        actor_user_id=actor_id,
    )
    result = _serialize_order(session, order_id)
    _store_command(session, actor_id, "create", idempotency_key, request_hash, order_id, result)
    session.commit()
    return result


def _locked_order(session: Session, order_id: str) -> dict[str, Any]:
    order = (
        session.execute(
            sa.select(models.corporate_purchase_orders)
            .where(
                models.corporate_purchase_orders.c.id == order_id,
                models.corporate_purchase_orders.c.organization_id == ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not order:
        raise BusinessError("corporate_purchase_not_found", "Corporate purchase was not found")
    return dict(order)


@_observe_corporate_mutation("approve")
def approve_corporate_purchase_order(
    session: Session,
    order_id: str,
    payload: dict[str, Any],
    actor_user_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.manage")
    bounded_payload(payload, {"expected_version"})
    command_payload = {**payload, "order_id": order_id}
    request_hash = _command_hash("approve", command_payload)
    replay = _command_replay(session, actor_id, "approve", idempotency_key, request_hash)
    if replay is not None:
        return replay
    order = _locked_order(session, order_id)
    expected_version = payload.get("expected_version")
    if type(expected_version) is not int or expected_version != order["version"]:
        raise BusinessError("corporate_purchase_version_conflict", "Order version changed")
    if order["status"] != "DRAFT":
        raise BusinessError(
            "corporate_purchase_not_approvable", "Only draft orders can be approved"
        )
    _validate_allocation_plan(session, order)
    now = _now()
    session.execute(
        sa.update(models.corporate_purchase_orders)
        .where(
            models.corporate_purchase_orders.c.id == order_id,
            models.corporate_purchase_orders.c.version == expected_version,
        )
        .values(
            status="APPROVED",
            version=expected_version + 1,
            approved_by=actor_id,
            approved_at=now,
            updated_at=now,
        )
    )
    _audit(
        session,
        "corporate_purchase.approved",
        "corporate_purchase_order",
        order_id,
        {"status": "APPROVED", "version": expected_version + 1},
        branch_id=None,
        actor_user_id=actor_id,
    )
    result = _serialize_order(session, order_id)
    _store_command(session, actor_id, "approve", idempotency_key, request_hash, order_id, result)
    session.commit()
    return result


@_observe_corporate_mutation("receive")
def receive_corporate_purchase_order(
    session: Session,
    order_id: str,
    payload: dict[str, Any],
    actor_user_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.manage")
    bounded_payload(payload, RECEIPT_KEYS)
    command_payload = {**payload, "order_id": order_id}
    request_hash = _command_hash("receive", command_payload)
    replay = _command_replay(session, actor_id, "receive", idempotency_key, request_hash)
    if replay is not None:
        return replay
    order = _locked_order(session, order_id)
    expected_version = payload.get("expected_version")
    if type(expected_version) is not int or expected_version != order["version"]:
        raise BusinessError("corporate_purchase_version_conflict", "Order version changed")
    if order["status"] not in {"APPROVED", "PARTIALLY_RECEIVED"}:
        raise BusinessError(
            "corporate_purchase_not_receivable", "Order is not available for receipt"
        )
    _validate_allocation_plan(session, order)
    branch_id = str(payload.get("branch_id", ""))
    warehouse_id = str(payload.get("warehouse_id", ""))
    if not session.scalar(
        sa.select(models.branches.c.id)
        .select_from(
            models.branches.join(
                models.warehouses, models.warehouses.c.branch_id == models.branches.c.id
            )
        )
        .where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == ORGANIZATION_ID,
            models.branches.c.legal_entity_id == order["legal_entity_id"],
            models.branches.c.status == "active",
            models.warehouses.c.id == warehouse_id,
            models.warehouses.c.organization_id == ORGANIZATION_ID,
            models.warehouses.c.status == "active",
        )
    ):
        raise BusinessError(
            "corporate_purchase_destination_invalid", "Receipt destination is invalid"
        )
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= MAX_LINES:
        raise BusinessError("corporate_purchase_receipt_lines_required", "Receipt requires lines")
    try:
        received_at = _parse_document_date(payload.get("received_at"), _now())
    except (ValueError, TypeError, OverflowError) as exc:
        raise BusinessError("corporate_purchase_date_invalid", "Invalid receipt date") from exc

    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in raw_lines:
        if not isinstance(raw_line, dict):
            raise BusinessError("corporate_purchase_receipt_line_invalid", "Invalid receipt line")
        bounded_payload(raw_line, RECEIPT_LINE_KEYS)
        allocation_id = str(raw_line.get("allocation_id", ""))
        if allocation_id in seen:
            raise BusinessError("corporate_purchase_receipt_line_invalid", "Duplicate allocation")
        allocation = (
            session.execute(
                sa.select(
                    models.corporate_purchase_allocations,
                    models.corporate_purchase_order_lines.c.order_id,
                    models.corporate_purchase_order_lines.c.item_id,
                    models.corporate_purchase_order_lines.c.presentation_id,
                    models.corporate_purchase_order_lines.c.presentation_snapshot,
                    models.corporate_purchase_order_lines.c.presentation_quantity.label(
                        "line_presentation_quantity"
                    ),
                    models.corporate_purchase_order_lines.c.inventory_cost.label(
                        "line_inventory_cost"
                    ),
                    models.corporate_purchase_order_lines.c.cost_per_base_unit,
                    models.corporate_purchase_order_lines.c.unit_price,
                )
                .select_from(
                    models.corporate_purchase_allocations.join(
                        models.corporate_purchase_order_lines,
                        models.corporate_purchase_order_lines.c.id
                        == models.corporate_purchase_allocations.c.order_line_id,
                    )
                )
                .where(
                    models.corporate_purchase_allocations.c.id == allocation_id,
                    models.corporate_purchase_order_lines.c.order_id == order_id,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if (
            not allocation
            or allocation["branch_id"] != branch_id
            or allocation["warehouse_id"] != warehouse_id
        ):
            raise BusinessError(
                "corporate_purchase_destination_invalid",
                "Allocation does not belong to destination",
            )
        quantity = purchase_decimal(raw_line.get("quantity"), "quantity", positive=True)
        pending = _quantity(
            Decimal(str(allocation["presentation_quantity"]))
            - Decimal(str(allocation["received_presentation_quantity"]))
        )
        if quantity > pending:
            raise BusinessError(
                "corporate_purchase_over_receipt", "Receipt exceeds allocated pending quantity"
            )
        cumulative_quantity = _quantity(
            Decimal(str(allocation["received_presentation_quantity"])) + quantity
        )
        allocation_base_quantity = Decimal(str(allocation["base_quantity"]))
        cumulative_base_quantity = (
            allocation_base_quantity
            if cumulative_quantity == Decimal(str(allocation["presentation_quantity"]))
            else _quantity(
                allocation_base_quantity
                * cumulative_quantity
                / Decimal(str(allocation["presentation_quantity"]))
            )
        )
        base_quantity = _quantity(
            cumulative_base_quantity - Decimal(str(allocation["received_base_quantity"]))
        )
        remaining_base_quantity = _quantity(
            allocation_base_quantity - cumulative_base_quantity
        )
        is_partial = cumulative_quantity < Decimal(str(allocation["presentation_quantity"]))
        if base_quantity <= 0 or (is_partial and remaining_base_quantity <= 0):
            raise BusinessError(
                "corporate_purchase_quantity_below_base_precision",
                "Receipt quantity is below the supported base-unit precision",
            )
        allocation_cost = _allocation_cost_target(session, dict(allocation))
        previous_cost = Decimal(
            str(
                session.scalar(
                    sa.select(
                        sa.func.coalesce(
                            sa.func.sum(models.corporate_purchase_receipt_lines.c.inventory_cost),
                            0,
                        )
                    ).where(
                        models.corporate_purchase_receipt_lines.c.allocation_id == allocation_id
                    )
                )
            )
        )
        cumulative_cost = (
            allocation_cost
            if cumulative_quantity == Decimal(str(allocation["presentation_quantity"]))
            else _money(
                allocation_cost
                * cumulative_quantity
                / Decimal(str(allocation["presentation_quantity"]))
            )
        )
        inventory_cost = _money(cumulative_cost - previous_cost)
        prepared.append(
            {
                **dict(allocation),
                "receipt_presentation_quantity": quantity,
                "receipt_base_quantity": base_quantity,
                "receipt_inventory_cost": inventory_cost,
                "cumulative_presentation_quantity": cumulative_quantity,
                "cumulative_base_quantity": cumulative_base_quantity,
            }
        )
        seen.add(allocation_id)

    _require_exact_storage(session, prepared)
    _acquire_inventory_advisory_locks(
        session, branch_id, warehouse_id, [row["item_id"] for row in prepared]
    )
    for row in prepared:
        if _physical_inventory_quantity(session, branch_id, warehouse_id, row["item_id"]) < 0:
            raise BusinessError(
                "negative_inventory_cost_policy_required",
                "Cannot receive while physical inventory is negative",
            )
    now = _now()
    receipt_id = _id()
    session.execute(
        models.corporate_purchase_receipts.insert().values(
            id=receipt_id,
            order_id=order_id,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            received_at=received_at,
            received_by=actor_id,
            created_at=now,
        )
    )
    movements = []
    for index, row in enumerate(prepared):
        current_quantity = _physical_inventory_quantity(
            session, branch_id, warehouse_id, row["item_id"]
        )
        state = (
            session.execute(
                sa.select(models.inventory_cost_states).where(
                    models.inventory_cost_states.c.branch_id == branch_id,
                    models.inventory_cost_states.c.warehouse_id == warehouse_id,
                    models.inventory_cost_states.c.item_id == row["item_id"],
                )
            )
            .mappings()
            .first()
        )
        current_average = _cost(state["average_unit_cost"]) if state else Decimal("0")
        entry_quantity = row["receipt_base_quantity"]
        entry_cost = row["receipt_inventory_cost"]
        new_quantity = purchase_decimal(
            _quantity(current_quantity + entry_quantity), "quantity_on_hand"
        )
        new_average = (
            _cost(entry_cost / entry_quantity)
            if current_quantity == 0
            else _cost(((current_quantity * current_average) + entry_cost) / new_quantity)
        )
        new_average = purchase_decimal(new_average, "average_unit_cost")
        _require_exact_storage(session, [new_quantity, new_average])
        movement_id = _id()
        movement = {
            "id": movement_id,
            "organization_id": ORGANIZATION_ID,
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "item_id": row["item_id"],
            "movement_type": "CORPORATE_PURCHASE_RECEIPT",
            "quantity_delta": entry_quantity,
            "unit_id": row["presentation_snapshot"]["base_unit_id"],
            "unit_cost": row["cost_per_base_unit"],
            "total_cost": entry_cost,
            "effective_at": received_at,
            "actor_user_id": actor_id,
            "document_type": "corporate_purchase_order",
            "document_id": order_id,
            "reference": order["folio"],
            "reason": "Recepción de compra corporativa",
            "notes": None,
            "idempotency_key": hashlib.sha256(
                f"corporate:{idempotency_key}:inventory:{index}".encode()
            ).hexdigest(),
            "status": "confirmed",
            "reversal_of_id": None,
            "source_type": "corporate_purchase_receipt",
            "source_id": receipt_id,
            "created_at": now,
        }
        session.execute(models.inventory_movements.insert().values(**movement))
        state_values = {
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "item_id": row["item_id"],
            "quantity_on_hand": new_quantity,
            "average_unit_cost": new_average,
            "last_unit_cost": row["cost_per_base_unit"],
            "last_supplier_id": order["supplier_id"],
            "last_cost_at": now,
            "updated_at": now,
        }
        if state:
            session.execute(
                sa.update(models.inventory_cost_states)
                .where(
                    models.inventory_cost_states.c.branch_id == branch_id,
                    models.inventory_cost_states.c.warehouse_id == warehouse_id,
                    models.inventory_cost_states.c.item_id == row["item_id"],
                )
                .values(**state_values)
            )
        else:
            session.execute(models.inventory_cost_states.insert().values(**state_values))
        receipt_line_id = _id()
        session.execute(
            models.corporate_purchase_receipt_lines.insert().values(
                id=receipt_line_id,
                receipt_id=receipt_id,
                allocation_id=row["id"],
                presentation_quantity=row["receipt_presentation_quantity"],
                base_quantity=entry_quantity,
                inventory_cost=entry_cost,
                inventory_movement_id=movement_id,
                created_at=now,
            )
        )
        session.execute(
            sa.update(models.corporate_purchase_allocations)
            .where(models.corporate_purchase_allocations.c.id == row["id"])
            .values(
                received_presentation_quantity=row["cumulative_presentation_quantity"],
                received_base_quantity=row["cumulative_base_quantity"],
                updated_at=now,
            )
        )
        session.execute(
            models.supplier_price_history.insert().values(
                id=_id(),
                presentation_id=row["presentation_id"],
                supplier_id=order["supplier_id"],
                net_price=row["unit_price"],
                cost_per_base_unit=row["cost_per_base_unit"],
                currency=order["currency"],
                effective_at=received_at,
                recorded_by=actor_id,
                organization_id=ORGANIZATION_ID,
                branch_id=branch_id,
                warehouse_id=warehouse_id,
                source_type="corporate_purchase_receipt",
                source_id=receipt_id,
                source_line_id=receipt_line_id,
                created_at=now,
            )
        )
        movements.append(movement_id)

    pending_exists = session.scalar(
        sa.select(models.corporate_purchase_allocations.c.id)
        .select_from(
            models.corporate_purchase_allocations.join(
                models.corporate_purchase_order_lines,
                models.corporate_purchase_order_lines.c.id
                == models.corporate_purchase_allocations.c.order_line_id,
            )
        )
        .where(
            models.corporate_purchase_order_lines.c.order_id == order_id,
            models.corporate_purchase_allocations.c.received_presentation_quantity
            < models.corporate_purchase_allocations.c.presentation_quantity,
        )
        .limit(1)
    )
    next_status = "PARTIALLY_RECEIVED" if pending_exists else "RECEIVED"
    session.execute(
        sa.update(models.corporate_purchase_orders)
        .where(
            models.corporate_purchase_orders.c.id == order_id,
            models.corporate_purchase_orders.c.version == expected_version,
        )
        .values(status=next_status, version=expected_version + 1, updated_at=now)
    )
    _audit(
        session,
        "corporate_purchase.received",
        "corporate_purchase_order",
        order_id,
        {
            "status": next_status,
            "version": expected_version + 1,
            "receipt_id": receipt_id,
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "line_count": len(prepared),
            "presentation_quantity": _quantity(
                sum(
                    (row["receipt_presentation_quantity"] for row in prepared),
                    Decimal("0"),
                )
            ),
            "base_quantity": _quantity(
                sum((row["receipt_base_quantity"] for row in prepared), Decimal("0"))
            ),
            "movement_ids": movements,
        },
        branch_id=branch_id,
        actor_user_id=actor_id,
    )
    order_result = _serialize_order(session, order_id)
    receipt_result = next(row for row in order_result["receipts"] if row["id"] == receipt_id)
    result = {"order": order_result, "receipt": receipt_result}
    _store_command(session, actor_id, "receive", idempotency_key, request_hash, order_id, result)
    session.commit()
    return result


@_observe_corporate_mutation("cancel")
def cancel_corporate_purchase_order(
    session: Session,
    order_id: str,
    payload: dict[str, Any],
    actor_user_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    _require_corporate_permission(session, actor_id, "purchases.corporate.manage")
    bounded_payload(payload, {"expected_version", "reason"})
    command_payload = {**payload, "order_id": order_id}
    request_hash = _command_hash("cancel", command_payload)
    replay = _command_replay(session, actor_id, "cancel", idempotency_key, request_hash)
    if replay is not None:
        return replay
    order = _locked_order(session, order_id)
    expected_version = payload.get("expected_version")
    reason = str(payload.get("reason", "")).strip()
    if type(expected_version) is not int or expected_version != order["version"]:
        raise BusinessError("corporate_purchase_version_conflict", "Order version changed")
    if not reason or len(reason) > 400:
        raise BusinessError(
            "corporate_purchase_cancellation_reason_required", "Cancellation reason is required"
        )
    if order["status"] != "DRAFT":
        raise BusinessError(
            "corporate_purchase_not_cancellable", "Only an unapproved draft can be cancelled"
        )
    now = _now()
    session.execute(
        sa.update(models.corporate_purchase_orders)
        .where(
            models.corporate_purchase_orders.c.id == order_id,
            models.corporate_purchase_orders.c.version == expected_version,
        )
        .values(
            status="CANCELLED",
            version=expected_version + 1,
            cancelled_by=actor_id,
            cancellation_reason=reason,
            cancelled_at=now,
            updated_at=now,
        )
    )
    _audit(
        session,
        "corporate_purchase.cancelled",
        "corporate_purchase_order",
        order_id,
        {"status": "CANCELLED", "version": expected_version + 1},
        branch_id=None,
        actor_user_id=actor_id,
    )
    result = _serialize_order(session, order_id)
    _store_command(session, actor_id, "cancel", idempotency_key, request_hash, order_id, result)
    session.commit()
    return result

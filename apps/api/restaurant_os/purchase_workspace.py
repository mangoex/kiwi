"""Read-only purchase calculations shared with the canonical document writer."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    _actor_user_id,
    _now,
    _parse_document_date,
    _sanitize_for_json,
    authorize_branch_scope,
)
from restaurant_os.presentation_rules import decimal_value, presentation_values

MAX_LINES = 200


def validate_purchase_payment(method: str, paid_from_cash: bool) -> None:
    if method not in {"cash", "transfer", "card", "other"}:
        raise BusinessError("workspace_payload_invalid", "Invalid payment method")
    if (method == "cash") != paid_from_cash:
        raise BusinessError(
            "cash_purchase_payment_mismatch", "Cash payment and paid_from_cash must agree"
        )


PURCHASE_KEYS = {
    "branch_id",
    "supplier_id",
    "document_type",
    "folio",
    "document_date",
    "payment_method",
    "paid_from_cash",
    "supplier_catalog_exception",
    "supplier_catalog_exception_reason",
    "freight_total",
    "notes",
    "evidence_url",
    "lines",
}
LINE_KEYS = {"presentation_id", "quantity", "unit_price", "discount", "tax"}


def bounded_payload(payload: dict[str, Any], allowed: set[str]) -> None:
    if set(payload) - allowed or len(json.dumps(payload, default=str).encode()) > 262144:
        raise BusinessError("workspace_payload_invalid", "Unsupported or oversized payload")


def purchase_decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    try:
        return decimal_value(value, field, positive=positive)
    except BusinessError as exc:
        raise BusinessError(
            "invalid_purchase_line", f"Invalid amount or quantity: {field}"
        ) from exc


def require_explicit_purchase_prices(payload: dict[str, Any]) -> None:
    if not payload.get("document_date"):
        raise BusinessError("purchase_document_date_invalid", "Explicit document date is required")
    required = {
        "branch_id",
        "supplier_id",
        "document_type",
        "folio",
        "document_date",
        "payment_method",
        "paid_from_cash",
        "lines",
    }
    if required - set(payload):
        raise BusinessError("workspace_payload_invalid", "All document inputs must be explicit")
    for field in (
        "branch_id",
        "supplier_id",
        "document_type",
        "folio",
        "document_date",
        "payment_method",
    ):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise BusinessError(
                "workspace_payload_invalid", "Document fields must be nonempty strings"
            )
    if not isinstance(payload["paid_from_cash"], bool):
        raise BusinessError("workspace_payload_invalid", "paid_from_cash must be boolean")
    if not isinstance(payload["lines"], list) or not 1 <= len(payload["lines"]) <= MAX_LINES:
        raise BusinessError("purchase_lines_required", "Purchase requires 1 to 200 lines")
    for line in payload.get("lines", []) if isinstance(payload.get("lines"), list) else []:
        if not isinstance(line, dict) or LINE_KEYS - set(line):
            raise BusinessError("invalid_purchase_line", "All line inputs must be explicit")
        for field in LINE_KEYS - {"presentation_id"}:
            if not isinstance(line[field], str) or not re.fullmatch(
                r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", line[field]
            ):
                raise BusinessError("invalid_purchase_line", "Line decimals must be exact strings")
        if not isinstance(line["presentation_id"], str):
            raise BusinessError("invalid_purchase_line", "Presentation ID must be a string")


def purchase_line_values(raw: dict[str, Any], presentation: dict[str, Any]) -> dict[str, Any]:
    bounded_payload(raw, LINE_KEYS)
    quantity = purchase_decimal(raw.get("quantity"), "quantity", positive=True)
    price = purchase_decimal(raw.get("unit_price", presentation["last_net_price"]), "unit_price")
    discount = purchase_decimal(raw.get("discount", "0"), "discount")
    tax = purchase_decimal(raw.get("tax", "0"), "tax")
    subtotal = purchase_decimal(quantity * price, "line_subtotal")
    if discount > subtotal:
        raise BusinessError("invalid_purchase_line", "Discount exceeds the line subtotal")
    base = purchase_decimal(
        quantity * Decimal(str(presentation["base_unit_yield"])), "base_quantity", positive=True
    )
    inventory_cost = purchase_decimal(subtotal - discount, "inventory_cost")
    return {
        "presentation_id": presentation["id"],
        "item_id": presentation["item_id"],
        "presentation_snapshot": _sanitize_for_json(presentation),
        "presentation_quantity": quantity,
        "base_quantity": base,
        "unit_price": price,
        "discount": discount,
        "tax": tax,
        "line_total": purchase_decimal(inventory_cost + tax, "line_total"),
        "inventory_cost": inventory_cost,
        "cost_per_base_unit": purchase_decimal(inventory_cost / base, "cost_per_base_unit"),
    }


def prepare_purchase(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str,
) -> dict[str, Any]:
    bounded_payload(payload, PURCHASE_KEYS)
    branch_id = str(payload.get("branch_id", ""))
    if not branch_id:
        raise BusinessError("purchase_supplier_or_branch_not_found", "A branch is required")
    authorize_branch_scope(session, actor_user_id, "purchases.manage", branch_id)
    supplier_id = str(payload.get("supplier_id", ""))
    supplier = session.scalar(
        sa.select(models.suppliers.c.id).where(
            models.suppliers.c.id == supplier_id,
            models.suppliers.c.organization_id == ORGANIZATION_ID,
            models.suppliers.c.status == "active",
        )
    )
    if not supplier:
        raise BusinessError("purchase_supplier_or_branch_not_found", "Active supplier is required")
    enabled = session.scalar(
        sa.select(models.supplier_branch_terms.c.is_enabled).where(
            models.supplier_branch_terms.c.supplier_id == supplier_id,
            models.supplier_branch_terms.c.branch_id == branch_id,
        )
    )
    if enabled is False:
        raise BusinessError(
            "supplier_not_enabled_for_branch", "Supplier is disabled for this branch"
        )
    document_type = str(payload.get("document_type", "receipt")).strip().lower()
    if document_type not in {"invoice", "receipt", "ticket", "note"}:
        raise BusinessError("invalid_purchase_document_type", "Purchase document type is invalid")
    folio = str(payload.get("folio", "")).strip()
    if not folio or len(folio) > 80:
        raise BusinessError(
            "purchase_folio_required", "Purchase folio is required, up to 80 characters"
        )
    freight = purchase_decimal(payload.get("freight_total", "0"), "freight_total")
    if freight != 0:
        raise BusinessError(
            "freight_cost_policy_required", "Freight allocation policy is not approved"
        )
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= MAX_LINES:
        raise BusinessError("purchase_lines_required", "Purchase requires 1 to 200 lines")
    paid = payload.get("paid_from_cash", False)
    if not isinstance(paid, bool):
        raise BusinessError("workspace_payload_invalid", "paid_from_cash must be boolean")
    method = str(payload.get("payment_method", "cash" if paid else "other")).lower()
    validate_purchase_payment(method, paid)
    supplier_catalog_exception = payload.get("supplier_catalog_exception", False)
    if not isinstance(supplier_catalog_exception, bool):
        raise BusinessError(
            "workspace_payload_invalid", "supplier_catalog_exception must be boolean"
        )
    raw_exception_reason = payload.get("supplier_catalog_exception_reason", "")
    if not isinstance(raw_exception_reason, str):
        raise BusinessError(
            "purchase_supplier_exception_reason_required", "Exception reason must be text"
        )
    exception_reason = raw_exception_reason.strip()
    if len(exception_reason) > 240:
        raise BusinessError(
            "purchase_supplier_exception_reason_required",
            "Exception reason must contain 1 to 240 characters",
        )
    if supplier_catalog_exception and not exception_reason:
        raise BusinessError(
            "purchase_supplier_exception_reason_required",
            "Exception reason is required",
        )
    if not supplier_catalog_exception and exception_reason:
        raise BusinessError(
            "workspace_payload_invalid", "Exception reason requires the explicit exception"
        )
    for field in ("notes", "evidence_url"):
        if payload.get(field) is not None and (
            not isinstance(payload[field], str) or len(payload[field]) > 600
        ):
            raise BusinessError("workspace_payload_invalid", f"Invalid field: {field}")

    lines = []
    subtotal = Decimal("0")
    discount = Decimal("0")
    tax = Decimal("0")
    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            raise BusinessError("invalid_purchase_line", f"Invalid line {index + 1}")
        presentation = (
            session.execute(
                sa.select(models.purchase_presentations).where(
                    models.purchase_presentations.c.id == str(raw.get("presentation_id", "")),
                    models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
                    models.purchase_presentations.c.status == "active",
                    models.purchase_presentations.c.supplier_id.in_(
                        sa.select(models.suppliers.c.id).where(
                            models.suppliers.c.organization_id == ORGANIZATION_ID,
                            models.suppliers.c.status == "active",
                        )
                    ),
                    ~sa.exists(
                        sa.select(models.supplier_branch_terms.c.supplier_id).where(
                            models.supplier_branch_terms.c.supplier_id
                            == models.purchase_presentations.c.supplier_id,
                            models.supplier_branch_terms.c.branch_id == branch_id,
                            models.supplier_branch_terms.c.is_enabled.is_(False),
                        )
                    ),
                )
            )
            .mappings()
            .first()
        )
        if not presentation:
            raise BusinessError(
                "purchase_presentation_not_found",
                f"Active supplier presentation was not found: line {index + 1}",
            )
        catalog_supplier_id = str(presentation["supplier_id"])
        is_exception_line = catalog_supplier_id != supplier_id
        if is_exception_line and not supplier_catalog_exception:
            raise BusinessError(
                "purchase_presentation_not_found",
                f"Active supplier presentation was not found: line {index + 1}",
            )
        presentation_values(session, dict(presentation), branch_id)
        snapshot = dict(presentation)
        snapshot.update(
            {
                "supplier_catalog_exception": is_exception_line,
                "purchase_supplier_id": supplier_id,
                "catalog_supplier_id": catalog_supplier_id,
                "supplier_catalog_exception_reason": (
                    exception_reason if is_exception_line else None
                ),
            }
        )
        snapshot["base_unit_code"] = session.scalar(
            sa.select(models.inventory_units.c.code).where(
                models.inventory_units.c.id == presentation["base_unit_id"],
                models.inventory_units.c.organization_id == ORGANIZATION_ID,
            )
        )
        line = purchase_line_values(raw, snapshot)
        lines.append(line)
        subtotal += line["inventory_cost"] + line["discount"]
        discount += line["discount"]
        tax += line["tax"]
    try:
        document_date = _parse_document_date(payload.get("document_date"), _now())
    except (ValueError, TypeError, OverflowError) as exc:
        raise BusinessError("purchase_document_date_invalid", "Invalid document date") from exc
    return {
        "branch_id": branch_id,
        "supplier_id": supplier_id,
        "document_type": document_type,
        "folio": folio,
        "document_date": document_date,
        "subtotal": purchase_decimal(subtotal, "subtotal"),
        "discount_total": purchase_decimal(discount, "discount_total"),
        "tax_total": purchase_decimal(tax, "tax_total"),
        "freight_total": freight,
        "total": purchase_decimal(subtotal - discount + tax, "total"),
        "paid_from_cash": paid,
        "payment_method": method,
        "supplier_catalog_exception": supplier_catalog_exception,
        "supplier_catalog_exception_reason": exception_reason or None,
        "lines": lines,
        "notes": payload.get("notes"),
        "evidence_url": payload.get("evidence_url"),
    }


def preview_result(values: dict[str, Any]) -> dict[str, Any]:
    result = _sanitize_for_json(values)
    fingerprint = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**result, "source": "python", "context_fingerprint": fingerprint}


def preview_purchase(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str,
) -> dict[str, Any]:
    require_explicit_purchase_prices(payload)
    values = prepare_purchase(session, payload, _actor_user_id(actor_user_id))
    return preview_result(
        {
            **values,
            "cash_total_cents": int(
                (values["total"] * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            ),
        }
    )


def preview_presentation(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str,
) -> dict[str, Any]:
    for field in ("base_unit_id", "commercial_unit_id"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise BusinessError("presentation_reference_not_found", "Explicit units are required")
    bounded_payload(
        payload,
        {
            "branch_id",
            "supplier_id",
            "item_id",
            "commercial_unit_id",
            "base_unit_id",
            "commercial_quantity",
            "usable_content",
            "base_unit_yield",
            "yield_percent",
            "last_net_price",
            "tax_rate",
            "gross_content",
            "net_content",
            "code",
            "name",
            "package_type",
            "barcode",
            "is_preferred",
            "status",
        },
    )
    branch = authorize_branch_scope(
        session, _actor_user_id(actor_user_id), "purchases.manage", payload.get("branch_id")
    )
    return preview_result(presentation_values(session, payload, branch))


def preview_recipe(
    session: Session,
    product_id: str,
    payload: dict[str, Any],
    actor_user_id: str,
) -> dict[str, Any]:
    from restaurant_os.operations import get_effective_product_recipe
    from restaurant_os.recipe_costing import recipe_cost_values

    bounded_payload(payload, {"branch_id", "yield_quantity", "yield_unit_id", "components"})
    branch_id = str(payload.get("branch_id") or "")
    if not branch_id:
        raise BusinessError("recipe_branch_required", "A branch is required for cost preview")
    get_effective_product_recipe(session, product_id, branch_id, actor_user_id)
    validate_recipe_inputs(session, payload, branch_id, explicit_units=True)
    yield_quantity = purchase_decimal(
        payload.get("yield_quantity"), "yield_quantity", positive=True
    )
    unit_id = str(payload.get("yield_unit_id") or "")
    raw_components = payload["components"]
    components = normalize_validated_recipe_components(session, raw_components, branch_id)
    costs = recipe_cost_values(session, components, branch_id, yield_quantity)
    return preview_result(
        {
            **costs,
            "yield_quantity": yield_quantity,
            "yield_unit_id": unit_id,
            "branch_id": branch_id,
            "product_id": product_id,
        }
    )


def preview_item_cost(
    session: Session,
    item_id: str,
    payload: dict[str, Any],
    actor_user_id: str,
) -> dict[str, Any]:
    from restaurant_os.operations import _branch_warehouse_id

    bounded_payload(
        payload, {"branch_id", "tax_rate", "waste_rate", "tax_percent", "waste_percent"}
    )
    branch_id = str(payload.get("branch_id") or "")
    if not branch_id:
        raise BusinessError("purchase_supplier_or_branch_not_found", "A branch is required")
    authorize_branch_scope(session, actor_user_id, "inventory.read", branch_id)
    item = (
        session.execute(
            sa.select(models.inventory_items).where(
                models.inventory_items.c.id == item_id,
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if not item or (item["catalog_scope"] == "branch" and item["source_branch_id"] != branch_id):
        raise BusinessError("inventory_item_not_found", "Inventory item is outside scope")
    warehouse_id = _branch_warehouse_id(session, branch_id)
    state = (
        session.execute(
            sa.select(models.inventory_cost_states).where(
                models.inventory_cost_states.c.branch_id == branch_id,
                models.inventory_cost_states.c.warehouse_id == warehouse_id,
                models.inventory_cost_states.c.item_id == item_id,
            )
        )
        .mappings()
        .first()
    )
    for prefix in ("tax", "waste"):
        if prefix + "_rate" not in payload and prefix + "_percent" not in payload:
            raise BusinessError(
                "workspace_payload_invalid", "Explicit tax and waste inputs required"
            )
    rate = fractional_rate(payload, "tax")
    waste = fractional_rate(payload, "waste")
    if waste >= 1:
        raise BusinessError("workspace_payload_invalid", "Waste rate must be below one")
    last_cost = purchase_decimal(state["last_unit_cost"] if state else "0", "last_unit_cost")
    return preview_result(
        {
            "item_id": item_id,
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "cost_source": "inventory_last_receipt" if state else "unavailable",
            "last_unit_cost": last_cost,
            "average_unit_cost": state["average_unit_cost"] if state else None,
            "cost_with_tax": purchase_decimal(last_cost * (1 + rate), "cost_with_tax")
            if state
            else None,
            "cost_with_waste": purchase_decimal(last_cost / (1 - waste), "cost_with_waste")
            if state
            else None,
            "tax_rate": rate,
            "waste_rate": waste,
        }
    )


def fractional_rate(payload: dict[str, Any], prefix: str) -> Decimal:
    percent_key, rate_key = prefix + "_percent", prefix + "_rate"
    if percent_key in payload:
        if rate_key in payload:
            raise BusinessError(
                "workspace_payload_invalid", "Rate and percent are mutually exclusive"
            )
        return purchase_decimal(
            purchase_decimal(str(payload[percent_key]).replace(",", "."), percent_key) / 100,
            rate_key,
        )
    return purchase_decimal(payload.get(rate_key, "0"), rate_key)


def validate_recipe_inputs(
    session: Session,
    payload: dict[str, Any],
    branch_id: str | None,
    *,
    explicit_units: bool = False,
) -> None:
    purchase_decimal(payload.get("yield_quantity"), "yield_quantity", positive=True)
    if not session.scalar(
        sa.select(models.inventory_units.c.id).where(
            models.inventory_units.c.id == str(payload.get("yield_unit_id") or ""),
            models.inventory_units.c.organization_id == ORGANIZATION_ID,
        )
    ):
        raise BusinessError("recipe_yield_unit_invalid", "Explicit yield unit is required")
    components = payload.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= MAX_LINES:
        raise BusinessError("recipe_components_required", "Recipe requires 1 to 200 components")
    for raw in components:
        if not isinstance(raw, dict):
            raise BusinessError("recipe_payload_invalid", "Components must be objects")
        bounded_payload(
            raw,
            {
                "item_id",
                "unit_id",
                "net_quantity",
                "quantity",
                "waste_rate",
                "waste_percent",
                "notes",
                "sort_order",
            },
        )
        purchase_decimal(
            raw.get("net_quantity", raw.get("quantity")), "net_quantity", positive=True
        )
        waste = fractional_rate(raw, "waste")
        if waste >= 1:
            raise BusinessError("recipe_payload_invalid", "Waste rate must be below one")
        item = (
            session.execute(
                sa.select(models.inventory_items).where(
                    models.inventory_items.c.id == str(raw.get("item_id") or ""),
                    models.inventory_items.c.organization_id == ORGANIZATION_ID,
                    models.inventory_items.c.status == "active",
                )
            )
            .mappings()
            .first()
        )
        if not item or (
            item["catalog_scope"] == "branch" and item["source_branch_id"] != branch_id
        ):
            raise BusinessError("recipe_component_not_found", "Component is outside recipe scope")
        unit = raw.get("unit_id", None if explicit_units else item["base_unit_id"])
        if str(unit) != item["base_unit_id"]:
            raise BusinessError("recipe_component_not_found", "Component base unit is required")


def normalize_validated_recipe_components(
    session: Session, raw: list[dict[str, Any]], branch_id: str | None
) -> list[dict[str, Any]]:
    from restaurant_os.operations import _normalize_recipe_components

    prepared = []
    for component in raw:
        values = {**component, "waste_rate": fractional_rate(component, "waste")}
        values.pop("waste_percent", None)
        prepared.append(values)
    components = _normalize_recipe_components(session, prepared, branch_id=branch_id)
    for component in components:
        purchase_decimal(component["gross_quantity"], "gross_quantity", positive=True)
    return components

"""Explicit relation and Decimal validation shared by presentation writers/previews."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID, BusinessError

QUANTUM = Decimal("0.000001")
MAX_DECIMAL = Decimal("999999999999.999999")


def decimal_value(
    value: Any, field: str, *, positive: bool = False, maximum: Decimal = MAX_DECIMAL
) -> Decimal:
    try:
        if value is None or isinstance(value, bool) or len(str(value)) > 80:
            raise ValueError
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < 0 or parsed > maximum:
            raise ValueError
        result = parsed.quantize(QUANTUM, rounding=ROUND_HALF_UP)
        if result > maximum or (positive and result <= 0):
            raise ValueError
        return result
    except (ValueError, InvalidOperation) as exc:
        raise BusinessError("invalid_purchase_presentation", f"Invalid decimal: {field}") from exc


def presentation_values(
    session: Session,
    payload: dict[str, Any],
    branch_id: str | None,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = {**(current or {}), **payload}
    if current:
        for field in ("supplier_id", "item_id", "base_unit_id", "commercial_unit_id", "code"):
            if field in payload and str(payload[field]) != str(current[field]):
                raise BusinessError(
                    "presentation_identity_immutable",
                    "Presentation references cannot be reassigned",
                )
    supplier_id = str(values.get("supplier_id") or "")
    supplier = (
        session.execute(
            sa.select(models.suppliers).where(
                models.suppliers.c.id == supplier_id,
                models.suppliers.c.organization_id == ORGANIZATION_ID,
                models.suppliers.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    item_id = str(values.get("item_id") or "")
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
    if not supplier or not item:
        raise BusinessError(
            "presentation_reference_not_found", "Active supplier and inventory item are required"
        )
    if branch_id:
        if item["catalog_scope"] == "branch" and item["source_branch_id"] != branch_id:
            raise BusinessError(
                "presentation_reference_not_found", "Inventory item is outside branch scope"
            )
        terms = session.execute(
            sa.select(models.supplier_branch_terms.c.is_enabled).where(
                models.supplier_branch_terms.c.supplier_id == supplier_id,
                models.supplier_branch_terms.c.branch_id == branch_id,
            )
        ).scalar_one_or_none()
        if terms is False:
            raise BusinessError(
                "supplier_not_enabled_for_branch", "Supplier is disabled for this branch"
            )

    # Omitted IDs may reuse the item's known base unit, never a guessed conversion.
    base_id = str(values.get("base_unit_id", item["base_unit_id"]))
    commercial_id = str(values.get("commercial_unit_id", base_id))
    unit_ids: set[str] = set(
        session.scalars(
            sa.select(models.inventory_units.c.id).where(
                models.inventory_units.c.organization_id == ORGANIZATION_ID,
                models.inventory_units.c.id.in_({base_id, commercial_id}),
            )
        )
    )
    if base_id != item["base_unit_id"] or {base_id, commercial_id} - unit_ids:
        raise BusinessError(
            "presentation_reference_not_found",
            "Explicit units must belong to the item and organization",
        )
    normalized: dict[str, Any] = {
        "supplier_id": supplier_id,
        "item_id": item_id,
        "base_unit_id": base_id,
        "commercial_unit_id": commercial_id,
        "usable_content": decimal_value(
            values.get("usable_content"), "usable_content", positive=True
        ),
        "base_unit_yield": decimal_value(
            values.get("base_unit_yield"), "base_unit_yield", positive=True
        ),
        "commercial_quantity": decimal_value(
            values.get("commercial_quantity", "1"), "commercial_quantity", positive=True
        ),
        "last_net_price": decimal_value(values.get("last_net_price", "0"), "last_net_price"),
        "yield_percent": decimal_value(
            values.get("yield_percent", "1"),
            "yield_percent",
            positive=True,
            maximum=Decimal("999.999999"),
        ),
        "tax_rate": decimal_value(
            values.get("tax_rate", "0"), "tax_rate", maximum=Decimal("999.999999")
        ),
    }
    for field in ("gross_content", "net_content"):
        value = values.get(field)
        normalized[field] = None if value is None else decimal_value(value, field, positive=True)
    normalized["cost_per_base_unit"] = decimal_value(
        normalized["last_net_price"] / normalized["usable_content"], "cost_per_base_unit"
    )
    return normalized

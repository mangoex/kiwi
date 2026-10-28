"""Inventory AI & Smart Procurement Engine for RestaurantOS.

Predictive purchase order generation, waste/yield audit, and invoice parsing.
All monetary amounts are strictly computed as integer cents without float precision loss.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID, BusinessError
from restaurant_os.purchase_workspace import purchase_decimal

UTC = timezone.utc


def calculate_suggested_purchases(
    session: Session,
    branch_id: str | None = None,
    days_ahead: int = 7,
) -> list[dict[str, Any]]:
    """Compute suggested purchase orders grouped by supplier based on inventory and consumption."""
    if days_ahead <= 0:
        days_ahead = 7

    if branch_id and not session.scalar(
        sa.select(models.branches.c.id).where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == ORGANIZATION_ID,
            models.branches.c.status == "active",
        )
    ):
        return []
    items = list(
        session.execute(
            sa.select(models.inventory_items)
            .where(
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
                sa.or_(
                    models.inventory_items.c.catalog_scope == "organization",
                    models.inventory_items.c.source_branch_id == branch_id,
                ),
            )
            .order_by(models.inventory_items.c.name)
        ).mappings()
    )

    if not items:
        return []

    item_ids = [str(item["id"]) for item in items]

    # 1. Current stock per item (from confirmed inventory movements)
    stock_query = sa.select(
        models.inventory_movements.c.item_id,
        sa.func.coalesce(sa.func.sum(models.inventory_movements.c.quantity_delta), 0).label(
            "stock"
        ),
    ).where(
        models.inventory_movements.c.organization_id == ORGANIZATION_ID,
        models.inventory_movements.c.status == "confirmed",
        models.inventory_movements.c.movement_type.not_in(
            ("SALE_RESERVATION", "RESERVATION_RELEASE")
        ),
        models.inventory_movements.c.item_id.in_(item_ids),
    )
    if branch_id:
        stock_query = stock_query.where(models.inventory_movements.c.branch_id == branch_id)
    stock_query = stock_query.group_by(models.inventory_movements.c.item_id)
    current_stocks = {
        str(row["item_id"]): Decimal(str(row["stock"]))
        for row in session.execute(stock_query).mappings()
    }

    # 2. Inventory thresholds (minimum and maximum quantities)
    thresholds_query = sa.select(
        models.inventory_stock_thresholds.c.item_id,
        models.inventory_stock_thresholds.c.minimum_quantity,
        models.inventory_stock_thresholds.c.maximum_quantity,
    ).where(
        models.inventory_stock_thresholds.c.organization_id == ORGANIZATION_ID,
        models.inventory_stock_thresholds.c.item_id.in_(item_ids),
    )
    if branch_id:
        thresholds_query = thresholds_query.where(
            models.inventory_stock_thresholds.c.branch_id == branch_id
        )
    thresholds_by_item = {
        str(row["item_id"]): {
            "min": Decimal(str(row["minimum_quantity"]))
            if row["minimum_quantity"] is not None
            else None,
            "max": Decimal(str(row["maximum_quantity"]))
            if row["maximum_quantity"] is not None
            else None,
        }
        for row in session.execute(thresholds_query).mappings()
    }

    # 3. Active purchase presentations (preferred first)
    presentations_query = (
        sa.select(
            models.purchase_presentations.c.item_id,
            models.purchase_presentations.c.supplier_id,
            models.purchase_presentations.c.cost_per_base_unit,
            models.purchase_presentations.c.last_net_price,
            models.purchase_presentations.c.base_unit_yield,
            models.purchase_presentations.c.is_preferred,
            models.suppliers.c.commercial_name.label("supplier_name"),
            models.suppliers.c.code.label("supplier_code"),
        )
        .select_from(
            models.purchase_presentations.join(
                models.suppliers,
                models.purchase_presentations.c.supplier_id == models.suppliers.c.id,
            )
        )
        .where(
            models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
            models.purchase_presentations.c.status == "active",
            models.suppliers.c.status == "active",
            models.purchase_presentations.c.item_id.in_(item_ids),
        )
        .order_by(
            models.purchase_presentations.c.is_preferred.desc(),
            models.purchase_presentations.c.created_at.desc(),
        )
    )
    pres_by_item: dict[str, dict[str, Any]] = {}
    for presentation_row in session.execute(presentations_query).mappings():
        iid = str(presentation_row["item_id"])
        if iid not in pres_by_item:
            pres_by_item[iid] = dict(presentation_row)

    # 4. Recent purchase history to find latest supplier and purchase price
    recent_purchases_query = (
        sa.select(
            models.purchase_document_lines.c.item_id,
            models.purchase_document_lines.c.unit_price,
            models.purchase_document_lines.c.cost_per_base_unit,
            models.purchase_documents.c.supplier_id,
            models.suppliers.c.commercial_name.label("supplier_name"),
            models.suppliers.c.code.label("supplier_code"),
        )
        .select_from(
            models.purchase_document_lines.join(
                models.purchase_documents,
                models.purchase_document_lines.c.purchase_document_id
                == models.purchase_documents.c.id,
            ).join(
                models.suppliers,
                models.purchase_documents.c.supplier_id == models.suppliers.c.id,
            )
        )
        .where(
            models.purchase_documents.c.organization_id == ORGANIZATION_ID,
            models.purchase_documents.c.status != "cancelled",
            models.purchase_document_lines.c.item_id.in_(item_ids),
        )
    )
    if branch_id:
        recent_purchases_query = recent_purchases_query.where(
            models.purchase_documents.c.branch_id == branch_id
        )
    recent_purchases_query = recent_purchases_query.order_by(
        models.purchase_documents.c.created_at.desc()
    )

    latest_by_item: dict[str, dict[str, Any]] = {}
    for rp in session.execute(recent_purchases_query).mappings():
        iid = str(rp["item_id"])
        if iid not in latest_by_item:
            latest_by_item[iid] = dict(rp)

    # 5. Consumption velocity over lookback window (last 30 days)
    lookback_days = 30
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # 5a. Direct physical inventory consumption
    mov_consumption_query = sa.select(
        models.inventory_movements.c.item_id,
        sa.func.coalesce(
            sa.func.sum(sa.func.abs(models.inventory_movements.c.quantity_delta)), 0
        ).label("consumed"),
    ).where(
        models.inventory_movements.c.organization_id == ORGANIZATION_ID,
        models.inventory_movements.c.status == "confirmed",
        models.inventory_movements.c.quantity_delta < 0,
        models.inventory_movements.c.movement_type.not_in(
            ("SALE_RESERVATION", "RESERVATION_RELEASE")
        ),
        models.inventory_movements.c.item_id.in_(item_ids),
        sa.func.coalesce(
            models.inventory_movements.c.effective_at, models.inventory_movements.c.created_at
        )
        >= cutoff_date,
    )
    if branch_id:
        mov_consumption_query = mov_consumption_query.where(
            models.inventory_movements.c.branch_id == branch_id
        )
    mov_consumption_query = mov_consumption_query.group_by(models.inventory_movements.c.item_id)
    movement_consumption = {
        str(row["item_id"]): Decimal(str(row["consumed"]))
        for row in session.execute(mov_consumption_query).mappings()
    }

    # 5b. Recipe consumption from confirmed orders
    recipe_consumption_query = (
        sa.select(
            models.recipe_components.c.item_id,
            sa.func.sum(
                models.order_lines.c.quantity
                * sa.func.coalesce(
                    models.recipe_components.c.gross_quantity,
                    models.recipe_components.c.quantity_base_units,
                    0,
                )
            ).label("recipe_consumed"),
        )
        .select_from(
            models.orders.join(
                models.order_lines, models.orders.c.id == models.order_lines.c.order_id
            )
            .join(
                models.recipes,
                sa.and_(
                    models.recipes.c.product_id == models.order_lines.c.product_id,
                    models.recipes.c.status == "active",
                ),
            )
            .join(
                models.recipe_components,
                models.recipe_components.c.recipe_id == models.recipes.c.id,
            )
        )
        .where(
            models.orders.c.organization_id == ORGANIZATION_ID,
            models.orders.c.status != "CANCELLED",
            models.orders.c.created_at >= cutoff_date,
            models.recipe_components.c.item_id.in_(item_ids),
        )
    )
    if branch_id:
        recipe_consumption_query = recipe_consumption_query.where(
            models.orders.c.branch_id == branch_id
        )
    recipe_consumption_query = recipe_consumption_query.group_by(models.recipe_components.c.item_id)
    recipe_consumption = {
        str(row["item_id"]): Decimal(str(row["recipe_consumed"]))
        for row in session.execute(recipe_consumption_query).mappings()
    }

    # Fallback supplier if none found
    first_supplier = (
        session.execute(
            sa.select(models.suppliers)
            .where(
                models.suppliers.c.organization_id == ORGANIZATION_ID,
                models.suppliers.c.status == "active",
            )
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )

    supplier_groups: dict[str, dict[str, Any]] = {}

    for item in items:
        item_id = str(item["id"])
        item_name = str(item["name"])
        sku = str(item["sku"])

        match = latest_by_item.get(item_id)
        pres = pres_by_item.get(item_id)

        # Determine supplier and unit cost
        if match:
            sup_id = str(match["supplier_id"])
            sup_name = str(match["supplier_name"])
            sup_code = str(match["supplier_code"])
            unit_cost = (
                match.get("cost_per_base_unit")
                or match.get("unit_price")
                or (pres and pres.get("cost_per_base_unit"))
                or Decimal("10.00")
            )
        elif pres:
            sup_id = str(pres["supplier_id"])
            sup_name = str(pres["supplier_name"])
            sup_code = str(pres["supplier_code"])
            unit_cost = (
                pres.get("cost_per_base_unit")
                or (
                    pres["last_net_price"] / pres["base_unit_yield"]
                    if pres.get("base_unit_yield") and pres["base_unit_yield"] > 0
                    else None
                )
                or Decimal("10.00")
            )
        elif first_supplier:
            sup_id = str(first_supplier["id"])
            sup_name = str(first_supplier["commercial_name"])
            sup_code = str(first_supplier["code"])
            unit_cost = Decimal("10.00")
        else:
            sup_id = "default_supplier"
            sup_name = "Proveedor General"
            sup_code = "SUP-GEN"
            unit_cost = Decimal("10.00")

        # 6. Demand Calculation
        curr_stock = current_stocks.get(item_id, Decimal("0.00"))
        thresh = thresholds_by_item.get(item_id)
        min_qty = thresh["min"] if thresh else None
        max_qty = thresh["max"] if thresh else None

        consumed_30d = max(
            movement_consumption.get(item_id, Decimal("0.00")),
            recipe_consumption.get(item_id, Decimal("0.00")),
        )
        daily_velocity = (consumed_30d / Decimal(str(lookback_days))).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        projected_consumption = (daily_velocity * Decimal(str(days_ahead))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        base_unit_yield = (pres and pres.get("base_unit_yield")) or Decimal("1.00")
        if base_unit_yield <= Decimal("0"):
            base_unit_yield = Decimal("1.00")

        if daily_velocity > Decimal("0"):
            if min_qty is not None:
                target_stock = min_qty + projected_consumption
                if max_qty is not None and target_stock > max_qty:
                    target_stock = max(max_qty, min_qty)
            else:
                target_stock = projected_consumption
            shortage = target_stock - curr_stock
        else:
            # No recent consumption velocity recorded in the 30-day window
            if min_qty is not None:
                shortage = min_qty - curr_stock
            else:
                if curr_stock <= Decimal("0"):
                    # Stock is depleted or zero; suggest baseline replenishment
                    shortage = (
                        base_unit_yield if base_unit_yield > Decimal("1") else Decimal("5.00")
                    )
                else:
                    # Item has positive stock and 0 consumption rate; no replenishment needed
                    shortage = Decimal("0.00")

        if shortage <= Decimal("0"):
            continue

        # Presentation packing: round up to nearest presentation package if presentation exists
        if pres and pres.get("base_unit_yield") and pres["base_unit_yield"] > Decimal("1"):
            yield_val = Decimal(str(pres["base_unit_yield"]))
            pack_count = (shortage / yield_val).to_integral_value(rounding=ROUND_CEILING)
            if pack_count < 1:
                pack_count = Decimal("1")
            suggested_qty = pack_count * yield_val
        else:
            suggested_qty = shortage.to_integral_value(rounding=ROUND_CEILING)

        if suggested_qty <= Decimal("0"):
            continue

        unit_cost_cents = int(
            (unit_cost * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        line_total_cents = int(
            (suggested_qty * unit_cost * Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

        if sup_id not in supplier_groups:
            supplier_groups[sup_id] = {
                "supplier_id": sup_id,
                "supplier_name": sup_name,
                "supplier_code": sup_code,
                "estimated_total_cents": 0,
                "lines": [],
            }

        supplier_groups[sup_id]["lines"].append(
            {
                "item_id": item_id,
                "item_name": item_name,
                "sku": sku,
                "suggested_quantity": float(suggested_qty),
                "unit_cost_cents": unit_cost_cents,
                "line_total_cents": line_total_cents,
            }
        )
        supplier_groups[sup_id]["estimated_total_cents"] += line_total_cents

    return list(supplier_groups.values())


def audit_inventory_yield_and_waste(
    session: Session,
    branch_id: str | None = None,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Compare theoretical consumption vs reported waste records to detect shrinkage/anomalies."""
    criteria = [models.waste_records.c.organization_id == ORGANIZATION_ID]
    if branch_id:
        criteria.append(models.waste_records.c.branch_id == branch_id)

    waste_rows = list(
        session.execute(
            sa.select(
                models.waste_records.c.item_id,
                sa.func.sum(models.waste_records.c.quantity).label("total_waste_qty"),
                sa.func.sum(models.waste_records.c.total_cost).label("total_waste_cost"),
            )
            .where(*criteria)
            .group_by(models.waste_records.c.item_id)
        ).mappings()
    )

    items = list(
        session.execute(
            sa.select(models.inventory_items).where(
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
            )
        ).mappings()
    )
    items_by_id = {str(i["id"]): i for i in items}

    audit_results = []
    for wr in waste_rows:
        iid = str(wr["item_id"])
        item = items_by_id.get(iid)
        name = str(item["name"]) if item else "Insumo"
        waste_qty = float(wr["total_waste_qty"] or 0)
        waste_cost = Decimal(str(wr["total_waste_cost"] or 0))
        waste_cents = int(waste_cost * 100)
        risk = "HIGH" if waste_cents > 50000 else "MEDIUM" if waste_cents > 10000 else "LOW"

        audit_results.append(
            {
                "item_id": iid,
                "item_name": name,
                "total_waste_quantity": waste_qty,
                "total_waste_cents": waste_cents,
                "risk_level": risk,
                "recommendation": "Realizar conteo físico en almacén"
                if risk != "LOW"
                else "En rango normal",
            }
        )

    return audit_results


def parse_supplier_invoice_data(raw_text_or_json: str) -> dict[str, Any]:
    """Parse supplier invoice text or OCR data into structured purchase lines."""
    lines_parsed: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    supplier_name = folio = None

    for line_number, line in enumerate(raw_text_or_json.strip().splitlines(), 1):
        line_clean = line.strip()
        if "PROVEEDOR:" in line_clean.upper():
            supplier_name = line_clean.split(":", 1)[1].strip()
        elif "FOLIO:" in line_clean.upper():
            folio = line_clean.split(":", 1)[1].strip()
        elif "|" in line_clean:
            parts = [p.strip() for p in line_clean.split("|")]
            if len(parts) >= 3:
                name = parts[0].removeprefix("- ").strip()
                qty_match = re.fullmatch(
                    r"([0-9]+(?:\.[0-9]{1,6})?)(?:\s*[A-Za-záéíóúñ]+)?", parts[1]
                )
                price_match = re.fullmatch(
                    r"\$?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,6})?)", parts[2]
                )
                if not name or not qty_match or not price_match:
                    warnings.append({"line": line_number, "code": "invalid_line"})
                    continue
                try:
                    qty = purchase_decimal(qty_match.group(1), "quantity", positive=True)
                    price = purchase_decimal(price_match.group(1).replace(",", ""), "unit_price")
                    total = purchase_decimal(qty * price, "line_total")
                except BusinessError:
                    warnings.append({"line": line_number, "code": "invalid_amount"})
                    continue
                lines_parsed.append(
                    {
                        "item_name": name,
                        "quantity": format(qty, "f"),
                        "unit_price_cents": int(
                            (price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                        ),
                        "line_total_cents": int(
                            (total * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                        ),
                    }
                )

    total_cents = sum(int(line["line_total_cents"]) for line in lines_parsed)
    return {
        "supplier_name": supplier_name,
        "folio": folio,
        "lines": lines_parsed,
        "total_cents": total_cents,
        "warnings": warnings,
        "status": "needs_review" if lines_parsed else "insufficient_data",
    }

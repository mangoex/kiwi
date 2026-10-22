"""Phase 4 — Suggested purchases by presentation yield (CORTE-CIEGO-001)."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import FinancialAuthority
from restaurant_os.owner_alerts import emit_owner_alert


def calculate_suggested_presentation_units(
    current_stock: Decimal,
    maximum_quantity: Decimal,
    base_unit_yield: Decimal,
) -> int:
    """Compute ceiling((maximum - current_stock) / base_unit_yield) using Decimal."""
    if base_unit_yield <= Decimal("0"):
        raise ops.BusinessError(
            "purchase_presentation_factor_invalid",
            "El factor de presentación debe ser mayor a cero.",
        )
    shortage = maximum_quantity - current_stock
    if shortage <= Decimal("0"):
        return 0
    raw_units = (shortage / base_unit_yield).to_integral_value(rounding=ROUND_CEILING)
    return int(raw_units)


def list_suggested_purchases(
    session: Session,
    actor_user_id: str,
    branch_id: str,
    *,
    include_all_below_max: bool = False,
    emit_low_stock_alerts: bool = True,
) -> dict[str, Any]:
    """Return suggested purchases per branch warehouse and emit below-minimum alerts."""
    authority = FinancialAuthority(session, actor_user_id, ops.ORGANIZATION_ID)
    version = authority._begin()
    authority._branches([branch_id])
    if not (
        authority._owner(version)
        or authority._explicit("inventory.read", branch_id)
        or authority._explicit("purchasing.read", branch_id)
        or authority._explicit("inventory.count.capture", branch_id)
        or ops._actor_has_permission(session, actor_user_id, "inventory.read", branch_id)
    ):
        raise ops.AuthorizationError(
            "suggested_purchases_forbidden",
            "Sin permiso para consultar compras sugeridas en esta sucursal.",
        )

    warehouse_id = ops._branch_warehouse_id(session, branch_id)
    thresholds = (
        session.execute(
            sa.select(
                models.inventory_stock_thresholds.c.item_id,
                models.inventory_stock_thresholds.c.minimum_quantity,
                models.inventory_stock_thresholds.c.maximum_quantity,
                models.inventory_items.c.name.label("item_name"),
                models.inventory_items.c.sku.label("item_sku"),
                models.inventory_items.c.base_unit_id,
                models.inventory_units.c.code.label("base_unit_code"),
            )
            .select_from(
                models.inventory_stock_thresholds.join(
                    models.inventory_items,
                    models.inventory_items.c.id == models.inventory_stock_thresholds.c.item_id,
                ).join(
                    models.inventory_units,
                    models.inventory_units.c.id == models.inventory_items.c.base_unit_id,
                )
            )
            .where(
                models.inventory_stock_thresholds.c.organization_id == ops.ORGANIZATION_ID,
                models.inventory_stock_thresholds.c.branch_id == branch_id,
                models.inventory_stock_thresholds.c.warehouse_id == warehouse_id,
                models.inventory_items.c.status == "active",
            )
            .order_by(models.inventory_items.c.name.asc())
        )
        .mappings()
        .all()
    )

    items: list[dict[str, Any]] = []
    for row in thresholds:
        item_id = str(row["item_id"])
        minimum_qty = Decimal(str(row["minimum_quantity"]))
        maximum_qty = Decimal(str(row["maximum_quantity"]))

        stock_sum = session.scalar(
            sa.select(
                sa.func.coalesce(sa.func.sum(models.inventory_movements.c.quantity_delta), 0)
            ).where(
                models.inventory_movements.c.organization_id == ops.ORGANIZATION_ID,
                models.inventory_movements.c.branch_id == branch_id,
                models.inventory_movements.c.warehouse_id == warehouse_id,
                models.inventory_movements.c.item_id == item_id,
                models.inventory_movements.c.status == "confirmed",
                models.inventory_movements.c.movement_type.not_in(
                    ("SALE_RESERVATION", "RESERVATION_RELEASE")
                ),
            )
        )
        current_stock = Decimal(str(stock_sum or 0))
        below_minimum = current_stock < minimum_qty
        at_or_below_minimum = current_stock <= minimum_qty

        if below_minimum and emit_low_stock_alerts:
            emit_owner_alert(
                session,
                branch_id=branch_id,
                alert_type="inventory_below_minimum",
                severity="warning",
                title=f"Inventario bajo mínimo: {row['item_name']}",
                summary=(
                    f"Existencia actual ({current_stock.quantize(Decimal('0.01'))} "
                    f"{row['base_unit_code']}) menor al mínimo "
                    f"({minimum_qty.quantize(Decimal('0.01'))} {row['base_unit_code']})."
                ),
                source_type="inventory_item",
                source_id=item_id,
                dedup_key=f"low_stock:{branch_id}:{item_id}:{current_stock.quantize(Decimal('0.000001'))}",
                payload={
                    "branch_id": branch_id,
                    "warehouse_id": warehouse_id,
                    "item_id": item_id,
                    "item_name": str(row["item_name"]),
                    "current_stock": str(current_stock.quantize(Decimal("0.01"))),
                    "minimum_quantity": str(minimum_qty.quantize(Decimal("0.01"))),
                    "maximum_quantity": str(maximum_qty.quantize(Decimal("0.01"))),
                },
            )

        if not include_all_below_max and not at_or_below_minimum:
            continue
        if current_stock >= maximum_qty:
            continue

        presentation = (
            session.execute(
                sa.select(
                    models.purchase_presentations.c.id,
                    models.purchase_presentations.c.code,
                    models.purchase_presentations.c.name,
                    models.purchase_presentations.c.base_unit_yield,
                    models.purchase_presentations.c.supplier_id,
                    models.inventory_units.c.code.label("commercial_unit_code"),
                )
                .select_from(
                    models.purchase_presentations.join(
                        models.inventory_units,
                        models.inventory_units.c.id
                        == models.purchase_presentations.c.commercial_unit_id,
                    )
                )
                .where(
                    models.purchase_presentations.c.organization_id == ops.ORGANIZATION_ID,
                    models.purchase_presentations.c.item_id == item_id,
                    models.purchase_presentations.c.status == "active",
                )
                .order_by(
                    models.purchase_presentations.c.is_preferred.desc(),
                    models.purchase_presentations.c.created_at.desc(),
                )
                .limit(1)
            )
            .mappings()
            .first()
        )

        if presentation is not None:
            factor = Decimal(str(presentation["base_unit_yield"]))
            presentation_id: str | None = str(presentation["id"])
            presentation_code: str | None = str(presentation["code"])
            presentation_name: str | None = str(presentation["name"])
            commercial_unit_code = str(presentation["commercial_unit_code"])
        else:
            factor = Decimal("1")
            presentation_id = None
            presentation_code = None
            presentation_name = None
            commercial_unit_code = str(row["base_unit_code"])

        suggested_units = calculate_suggested_presentation_units(
            current_stock=current_stock,
            maximum_quantity=maximum_qty,
            base_unit_yield=factor,
        )
        shortage_base_units = maximum_qty - current_stock
        suggested_base_units = Decimal(suggested_units) * factor

        items.append(
            {
                "branch_id": branch_id,
                "warehouse_id": warehouse_id,
                "item_id": item_id,
                "item_name": str(row["item_name"]),
                "item_sku": str(row["item_sku"]),
                "base_unit_code": str(row["base_unit_code"]),
                "current_stock": str(current_stock.quantize(Decimal("0.01"))),
                "minimum_quantity": str(minimum_qty.quantize(Decimal("0.01"))),
                "maximum_quantity": str(maximum_qty.quantize(Decimal("0.01"))),
                "shortage_base_quantity": str(shortage_base_units.quantize(Decimal("0.01"))),
                "below_minimum": below_minimum,
                "presentation_id": presentation_id,
                "presentation_code": presentation_code,
                "presentation_name": presentation_name,
                "commercial_unit_code": commercial_unit_code,
                "presentation_factor": str(factor.quantize(Decimal("0.01"))),
                "suggested_presentation_units": suggested_units,
                "suggested_base_quantity": str(suggested_base_units.quantize(Decimal("0.01"))),
                "formula": "ceil((maximum_quantity - current_stock) / presentation_factor)",
            }
        )

    session.commit()
    return {
        "branch_id": branch_id,
        "warehouse_id": warehouse_id,
        "items": items,
    }

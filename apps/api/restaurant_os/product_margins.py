"""Phase 5 — Reliable product margins and <50% Owner alert (CORTE-CIEGO-001)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import FinancialAuthority
from restaurant_os.owner_alerts import emit_owner_alert
from restaurant_os.recipe_costing import recipe_cost_values

MARGIN_ALERT_THRESHOLD_PCT = Decimal("50.00")


def _active_product_price_cents(session: Session, product_id: str) -> int | None:
    price = session.scalar(
        sa.select(models.price_versions.c.price_cents)
        .where(
            models.price_versions.c.organization_id == ops.ORGANIZATION_ID,
            models.price_versions.c.product_id == product_id,
            models.price_versions.c.valid_to.is_(None),
        )
        .order_by(models.price_versions.c.valid_from.desc())
        .limit(1)
    )
    if price is None:
        return None
    return int(price)


def _active_sale_recipe(session: Session, product_id: str, branch_id: str) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.select(
                models.recipes.c.id,
                models.recipes.c.version,
                models.recipes.c.yield_quantity,
                models.recipes.c.branch_id,
            )
            .where(
                models.recipes.c.organization_id == ops.ORGANIZATION_ID,
                models.recipes.c.product_id == product_id,
                models.recipes.c.status == "active",
                sa.or_(
                    models.recipes.c.branch_id == branch_id,
                    models.recipes.c.branch_id.is_(None),
                ),
                models.recipes.c.valid_to.is_(None),
            )
            .order_by(
                sa.case((models.recipes.c.branch_id == branch_id, 0), else_=1),
                models.recipes.c.version.desc(),
            )
            .limit(1)
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def evaluate_product_margins(
    session: Session,
    actor_user_id: str,
    branch_id: str,
    *,
    product_id: str | None = None,
    emit_alerts: bool = True,
) -> dict[str, Any]:
    """Compute product margins with incomplete-cost guard and <50% Owner alert."""
    authority = FinancialAuthority(session, actor_user_id, ops.ORGANIZATION_ID)
    authority.require_financial([(branch_id, "reconciliation")])

    stmt = (
        sa.select(
            models.products.c.id,
            models.products.c.name,
            models.products.c.sku,
            models.products.c.status,
        )
        .where(
            models.products.c.organization_id == ops.ORGANIZATION_ID,
            models.products.c.status == "active",
        )
        .order_by(models.products.c.name.asc())
    )
    if product_id is not None:
        stmt = stmt.where(models.products.c.id == product_id)

    products = session.execute(stmt).mappings().all()
    results: list[dict[str, Any]] = []

    for prod in products:
        pid = str(prod["id"])
        pname = str(prod["name"])
        psku = str(prod["sku"])
        price_cents = _active_product_price_cents(session, pid)
        recipe = _active_sale_recipe(session, pid, branch_id)

        if price_cents is None or price_cents <= 0:
            results.append(
                {
                    "branch_id": branch_id,
                    "product_id": pid,
                    "product_name": pname,
                    "product_sku": psku,
                    "sale_price_cents": price_cents,
                    "sale_price_mxn": None,
                    "recipe_cost_mxn": None,
                    "cost_complete": False,
                    "margin_reliable": False,
                    "incomplete_reason": "missing_or_zero_sale_price",
                    "margin_pct": None,
                    "below_threshold": False,
                }
            )
            continue

        sale_price_mxn = (Decimal(price_cents) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if recipe is None:
            results.append(
                {
                    "branch_id": branch_id,
                    "product_id": pid,
                    "product_name": pname,
                    "product_sku": psku,
                    "sale_price_cents": price_cents,
                    "sale_price_mxn": str(sale_price_mxn),
                    "recipe_cost_mxn": None,
                    "cost_complete": False,
                    "margin_reliable": False,
                    "incomplete_reason": "missing_active_recipe",
                    "margin_pct": None,
                    "below_threshold": False,
                }
            )
            continue

        comp_rows = (
            session.execute(
                sa.select(
                    models.recipe_components.c.item_id,
                    models.recipe_components.c.unit_id,
                    models.recipe_components.c.net_quantity,
                    models.recipe_components.c.gross_quantity,
                    models.recipe_components.c.waste_rate,
                    models.inventory_items.c.name.label("item_name"),
                    models.inventory_units.c.code.label("unit_code"),
                )
                .select_from(
                    models.recipe_components.join(
                        models.inventory_items,
                        models.inventory_items.c.id == models.recipe_components.c.item_id,
                    ).join(
                        models.inventory_units,
                        models.inventory_units.c.id == models.recipe_components.c.unit_id,
                    )
                )
                .where(models.recipe_components.c.recipe_id == str(recipe["id"]))
                .order_by(models.recipe_components.c.sort_order.asc())
            )
            .mappings()
            .all()
        )

        if not comp_rows:
            results.append(
                {
                    "branch_id": branch_id,
                    "product_id": pid,
                    "product_name": pname,
                    "product_sku": psku,
                    "sale_price_cents": price_cents,
                    "sale_price_mxn": str(sale_price_mxn),
                    "recipe_cost_mxn": None,
                    "cost_complete": False,
                    "margin_reliable": False,
                    "incomplete_reason": "empty_recipe_components",
                    "margin_pct": None,
                    "below_threshold": False,
                }
            )
            continue

        cost_info = recipe_cost_values(
            session,
            [dict(c) for c in comp_rows],
            branch_id,
            Decimal(str(recipe["yield_quantity"])),
        )
        breakdown = cost_info["breakdown"]
        missing_components = [
            b["item_id"]
            for b in breakdown
            if b.get("cost_source") == "unavailable"
            or Decimal(str(b.get("unit_cost", "0"))) <= Decimal("0")
        ]

        if missing_components:
            results.append(
                {
                    "branch_id": branch_id,
                    "product_id": pid,
                    "product_name": pname,
                    "product_sku": psku,
                    "sale_price_cents": price_cents,
                    "sale_price_mxn": str(sale_price_mxn),
                    "recipe_cost_mxn": None,
                    "cost_complete": False,
                    "margin_reliable": False,
                    "incomplete_reason": "missing_component_cost",
                    "missing_component_item_ids": missing_components,
                    "margin_pct": None,
                    "below_threshold": False,
                }
            )
            continue

        unit_recipe_cost = Decimal(str(cost_info["cost_per_yield_unit"]))
        margin_ratio = (sale_price_mxn - unit_recipe_cost) / sale_price_mxn
        margin_pct = (margin_ratio * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        below_threshold = margin_pct < MARGIN_ALERT_THRESHOLD_PCT

        if below_threshold and emit_alerts:
            emit_owner_alert(
                session,
                branch_id=branch_id,
                alert_type="product_margin_below_threshold",
                severity="warning",
                title=f"Margen de producto menor a 50%: {pname}",
                summary=(
                    f"El producto {pname} tiene un margen confiable de {margin_pct}% "
                    f"(precio ${sale_price_mxn} MXN, "
                    f"costo ${unit_recipe_cost.quantize(Decimal('0.01'))} MXN)."
                ),
                source_type="product",
                source_id=pid,
                dedup_key=f"margin:{branch_id}:{pid}:{recipe['version']}:{price_cents}:{unit_recipe_cost}",
                payload={
                    "branch_id": branch_id,
                    "product_id": pid,
                    "product_name": pname,
                    "recipe_id": str(recipe["id"]),
                    "recipe_version": int(recipe["version"]),
                    "sale_price_mxn": str(sale_price_mxn),
                    "recipe_cost_mxn": str(unit_recipe_cost.quantize(Decimal("0.01"))),
                    "margin_pct": str(margin_pct),
                    "threshold_pct": str(MARGIN_ALERT_THRESHOLD_PCT),
                },
            )

        results.append(
            {
                "branch_id": branch_id,
                "product_id": pid,
                "product_name": pname,
                "product_sku": psku,
                "recipe_id": str(recipe["id"]),
                "recipe_version": int(recipe["version"]),
                "sale_price_cents": price_cents,
                "sale_price_mxn": str(sale_price_mxn),
                "recipe_cost_mxn": str(unit_recipe_cost.quantize(Decimal("0.01"))),
                "cost_complete": True,
                "margin_reliable": True,
                "incomplete_reason": None,
                "margin_pct": str(margin_pct),
                "below_threshold": below_threshold,
            }
        )

    session.commit()
    return {
        "branch_id": branch_id,
        "threshold_pct": str(MARGIN_ALERT_THRESHOLD_PCT),
        "products": results,
    }

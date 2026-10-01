"""Read-only recipe cost calculation reused by previews and recorded calculations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    _branch_warehouse_id,
    _cost,
    _sanitize_for_json,
)


def recipe_cost_values(
    session: Session,
    components: list[dict[str, Any]],
    branch_id: str,
    yield_quantity: Decimal,
) -> dict[str, Any]:
    warehouse_id = _branch_warehouse_id(session, branch_id)
    before_waste = Decimal("0")
    total = Decimal("0")
    breakdown = []
    for component in components:
        average = session.scalar(
            sa.select(models.inventory_cost_states.c.average_unit_cost).where(
                models.inventory_cost_states.c.branch_id == branch_id,
                models.inventory_cost_states.c.warehouse_id == warehouse_id,
                models.inventory_cost_states.c.item_id == component["item_id"],
            )
        )
        source = "inventory_average"
        if not average or average <= 0:
            source = "presentation_informative"
            average = session.scalar(
                sa.select(models.purchase_presentations.c.cost_per_base_unit)
                .where(
                    models.purchase_presentations.c.item_id == component["item_id"],
                    models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
                    models.purchase_presentations.c.status == "active",
                )
                .order_by(
                    models.purchase_presentations.c.is_preferred.desc(),
                    models.purchase_presentations.c.created_at.desc(),
                )
                .limit(1)
            )
            if average is None:
                source = "unavailable"
        unit_cost = _cost(average or 0)
        net_cost = _cost(Decimal(str(component["net_quantity"])) * unit_cost)
        gross_cost = _cost(Decimal(str(component["gross_quantity"])) * unit_cost)
        before_waste += net_cost
        total += gross_cost
        breakdown.append(
            _sanitize_for_json(
                {
                    "item_id": component["item_id"],
                    "item_name": component.get("item_name"),
                    "unit_id": component["unit_id"],
                    "unit_code": component.get("unit_code"),
                    "net_quantity": component["net_quantity"],
                    "gross_quantity": component["gross_quantity"],
                    "waste_rate": component["waste_rate"],
                    "unit_cost": unit_cost,
                    "cost_before_waste": net_cost,
                    "waste_cost": _cost(gross_cost - net_cost),
                    "total_cost": gross_cost,
                    "cost_source": source,
                }
            )
        )
    before_waste = _cost(before_waste)
    total = _cost(total)
    return {
        "cost_before_waste": before_waste,
        "waste_cost": _cost(total - before_waste),
        "total_cost": total,
        "cost_per_yield_unit": _cost(total / yield_quantity),
        "breakdown": breakdown,
    }

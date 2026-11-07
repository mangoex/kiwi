"""Unified Copilot Tools Engine for RestaurantOS.

Provides deterministically verified database tools with OpenAI/Gemini function-calling schemas
for inventory thresholds, stock, cash registers, sales, recipes and purchasing.
Side-by-side compatible with GrokBot without modifying GrokBot boundaries.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.inventory_ai import calculate_suggested_purchases
from restaurant_os.recipe_ai import (
    calculate_theoretical_recipe_cost,
    parse_recipe_text,
)

UTC = datetime.timezone.utc

# ---------------------------------------------------------------------------
# Tool Definitions Schema (OpenAI / Gemini function format)
# ---------------------------------------------------------------------------

COPILOT_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_inventory_stock_and_thresholds",
            "description": "Consulta umbrales mínimos, máximos, unidades de medida y existencias de insumos de inventario para una o todas las sucursales (ej. Chapultepec).",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name_or_id": {
                        "type": "string",
                        "description": "Nombre o ID de la sucursal (ej. 'Chapultepec', 'Centro', 'Norte'). Omitir para ver todas.",
                    },
                    "search_term": {
                        "type": "string",
                        "description": "Término de búsqueda opcional para filtrar insumos (ej. 'aderezo', 'queso', 'aguacate').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cash_status",
            "description": "Consulta el estado de cajas registradoras abiertas, cajeros, fondo inicial y últimos cortes de caja del día.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name_or_id": {
                        "type": "string",
                        "description": "Nombre o ID de la sucursal opcional.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_performance",
            "description": "Consulta ventas totales, ticket promedio y desglose por canal de venta (POS local, Rappi, Uber Eats, DiDi).",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name_or_id": {
                        "type": "string",
                        "description": "Nombre o ID de la sucursal opcional.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Número de días hacia atrás a consultar (default: 1, hoy).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recipes_list",
            "description": "Consulta recetas registradas, ingredientes por platillo y costo teórico de preparación.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Nombre o fragmento del producto o platillo (ej. 'hamburguesa', 'pizza').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_suggested_purchases",
            "description": "Calcula compras sugeridas agrupadas por proveedor según existencias y consumo proyectado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name_or_id": {
                        "type": "string",
                        "description": "Sucursal para proyectar compras.",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Días de proyección de demanda (default: 7).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_recipe",
            "description": "Estructura y registra una propuesta de receta analizando ingredientes y unidades culinarias en lenguaje natural.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Nombre del producto en el menú.",
                    },
                    "recipe_text": {
                        "type": "string",
                        "description": "Descripción de la receta e ingredientes en lenguaje natural (ej. '250g de masa, 150g de queso mozzarella, 80g de salsa').",
                    },
                    "branch_name_or_id": {
                        "type": "string",
                        "description": "Sucursal opcional para receta exclusiva.",
                    },
                },
                "required": ["product_name", "recipe_text"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: Resolver Sucursal
# ---------------------------------------------------------------------------

def _resolve_branch(
    session: Session, organization_id: str, branch_name_or_id: str | None
) -> tuple[str | None, str]:
    if not branch_name_or_id or branch_name_or_id.strip().lower() in ("todas", "all", ""):
        return None, "Todas las sucursales"

    target = branch_name_or_id.strip()

    # Exact ID match
    row = session.execute(
        sa.select(models.branches.c.id, models.branches.c.name).where(
            models.branches.c.organization_id == organization_id,
            models.branches.c.id == target,
            models.branches.c.status == "active",
        )
    ).first()
    if row:
        return str(row[0]), str(row[1])

    # Name match (case-insensitive)
    row = session.execute(
        sa.select(models.branches.c.id, models.branches.c.name).where(
            models.branches.c.organization_id == organization_id,
            sa.func.lower(models.branches.c.name).like(f"%{target.lower()}%"),
            models.branches.c.status == "active",
        )
    ).first()
    if row:
        return str(row[0]), str(row[1])

    return None, target


# ---------------------------------------------------------------------------
# Implementación de Herramientas
# ---------------------------------------------------------------------------

def tool_get_inventory_thresholds_and_stock(
    session: Session,
    organization_id: str,
    branch_name_or_id: str | None = None,
    search_term: str | None = None,
) -> dict[str, Any]:
    """Retrieve configured inventory thresholds (min, max) and stock for supplies."""
    branch_id, branch_label = _resolve_branch(session, organization_id, branch_name_or_id)

    thresholds = models.inventory_stock_thresholds
    items = models.inventory_items
    units = models.inventory_units
    branches = models.branches
    states = models.inventory_cost_states

    query = (
        sa.select(
            items.c.name.label("item_name"),
            items.c.sku.label("sku"),
            sa.func.coalesce(units.c.name, units.c.code).label("unit_name"),
            units.c.code.label("unit_code"),
            thresholds.c.minimum_quantity.label("min_qty"),
            thresholds.c.maximum_quantity.label("max_qty"),
            sa.func.coalesce(states.c.quantity_on_hand, 0).label("stock"),
            branches.c.name.label("branch_name"),
            thresholds.c.updated_at.label("updated_at"),
        )
        .select_from(
            thresholds.join(items, items.c.id == thresholds.c.item_id)
            .outerjoin(units, units.c.id == items.c.base_unit_id)
            .outerjoin(branches, branches.c.id == thresholds.c.branch_id)
            .outerjoin(
                states,
                sa.and_(
                    states.c.item_id == thresholds.c.item_id,
                    states.c.branch_id == thresholds.c.branch_id,
                    states.c.warehouse_id == thresholds.c.warehouse_id,
                ),
            )
        )
        .where(
            thresholds.c.organization_id == organization_id,
            items.c.status == "active",
        )
    )

    if branch_id:
        query = query.where(thresholds.c.branch_id == branch_id)

    if search_term:
        st = f"%{search_term.strip().lower()}%"
        query = query.where(
            sa.or_(
                sa.func.lower(items.c.name).like(st),
                sa.func.lower(items.c.sku).like(st),
            )
        )

    rows = session.execute(query.order_by(items.c.name.asc())).all()

    formatted_items = []
    for r in rows:
        min_v = float(r.min_qty) if r.min_qty is not None else 0.0
        max_v = float(r.max_qty) if r.max_qty is not None else 0.0
        stock_v = float(r.stock) if r.stock is not None else 0.0
        unit_str = str(r.unit_code or r.unit_name or "u")
        formatted_items.append(
            {
                "insumo": str(r.item_name),
                "sku": str(r.sku or "-"),
                "minimo": min_v,
                "maximo": max_v,
                "unidad": unit_str,
                "existencia_actual": stock_v,
                "sucursal": str(r.branch_name or branch_label),
            }
        )

    return {
        "branch_name": branch_label,
        "total_configured_thresholds": len(formatted_items),
        "items": formatted_items,
        "nota": "Estos son los umbrales mínimos y máximos de insumos configurados en inventario.",
    }


def tool_get_cash_status(
    session: Session,
    organization_id: str,
    branch_name_or_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve open cash shifts, drawer balances, and finalized cash cuts."""
    branch_id, branch_label = _resolve_branch(session, organization_id, branch_name_or_id)

    shifts = models.cash_shifts
    branches = models.branches
    users = models.users

    # 1. Open shifts
    open_query = (
        sa.select(
            shifts.c.id,
            shifts.c.register_code,
            shifts.c.status,
            shifts.c.opening_cash_cents,
            shifts.c.opened_at,
            branches.c.name.label("branch_name"),
            users.c.display_name.label("cashier_name"),
        )
        .select_from(
            shifts.join(branches, branches.c.id == shifts.c.branch_id)
            .outerjoin(users, users.c.id == shifts.c.cashier_user_id)
        )
        .where(
            shifts.c.organization_id == organization_id,
            sa.func.upper(shifts.c.status).in_(("OPEN", "CLOSING")),
        )
    )

    if branch_id:
        open_query = open_query.where(shifts.c.branch_id == branch_id)

    open_rows = session.execute(open_query.order_by(shifts.c.opened_at.desc())).all()

    open_registers = []
    for s in open_rows:
        fondo = (s.opening_cash_cents or 0) / 100
        opened_str = s.opened_at.strftime("%H:%M") if s.opened_at else "-"
        open_registers.append(
            {
                "caja": str(s.register_code),
                "sucursal": str(s.branch_name),
                "cajero": str(s.cashier_name or "Sin asignar"),
                "estado": str(s.status),
                "fondo_inicial": f"${fondo:,.2f}",
                "hora_apertura": opened_str,
            }
        )

    # 2. Recent cash cuts
    cuts = models.user_cash_cuts
    cuts_query = (
        sa.select(
            cuts.c.register_code_snapshot.label("register_code"),
            cuts.c.finalized_at,
            cuts.c.expected_cash_cents,
            cuts.c.counted_cash_cents,
            cuts.c.difference_cents,
            branches.c.name.label("branch_name"),
        )
        .select_from(cuts.join(branches, branches.c.id == cuts.c.branch_id))
        .where(
            cuts.c.organization_id == organization_id,
            cuts.c.status == "FINALIZED",
        )
    )
    if branch_id:
        cuts_query = cuts_query.where(cuts.c.branch_id == branch_id)

    recent_cuts = []
    for c in session.execute(cuts_query.order_by(cuts.c.finalized_at.desc()).limit(10)).all():
        diff = (c.difference_cents or 0) / 100
        recent_cuts.append(
            {
                "caja": str(c.register_code or "Caja"),
                "sucursal": str(c.branch_name),
                "diferencia": f"${diff:+,.2f}",
                "cerrado_el": c.finalized_at.strftime("%Y-%m-%d %H:%M") if c.finalized_at else "-",
            }
        )

    return {
        "branch_name": branch_label,
        "open_registers_count": len(open_registers),
        "open_registers": open_registers,
        "recent_closed_cuts": recent_cuts,
    }


def tool_get_sales_performance(
    session: Session,
    organization_id: str,
    branch_name_or_id: str | None = None,
    days: int = 1,
) -> dict[str, Any]:
    """Retrieve sales KPIs, revenue, order counts and sales channels."""
    branch_id, branch_label = _resolve_branch(session, organization_id, branch_name_or_id)
    since = datetime.datetime.now(UTC) - datetime.timedelta(days=max(1, days))

    orders = models.orders
    branches = models.branches

    query = (
        sa.select(
            sa.func.count(orders.c.id).label("total_orders"),
            sa.func.coalesce(sa.func.sum(orders.c.total_cents), 0).label("total_sales_cents"),
            sa.func.coalesce(orders.c.channel, "pos").label("channel"),
        )
        .where(
            orders.c.organization_id == organization_id,
            orders.c.status.in_(("completed", "delivered", "accepted", "preparing", "ready")),
            orders.c.created_at >= since,
        )
    )
    if branch_id:
        query = query.where(orders.c.branch_id == branch_id)

    query = query.group_by(orders.c.channel)
    rows = session.execute(query).all()

    total_orders = sum(int(r.total_orders) for r in rows)
    total_cents = sum(int(r.total_sales_cents) for r in rows)
    channels_breakdown = {
        str(r.channel).upper(): {
            "pedidos": int(r.total_orders),
            "total": f"${(int(r.total_sales_cents) / 100):,.2f}",
        }
        for r in rows
    }

    avg_ticket = (total_cents / total_orders / 100) if total_orders > 0 else 0.0

    return {
        "branch_name": branch_label,
        "periodo_dias": days,
        "total_pedidos": total_orders,
        "ventas_totales": f"${(total_cents / 100):,.2f}",
        "ticket_promedio": f"${avg_ticket:,.2f}",
        "canales": channels_breakdown,
    }


def tool_get_recipes_list(
    session: Session,
    organization_id: str,
    search_term: str | None = None,
) -> dict[str, Any]:
    """Retrieve active sale recipes, ingredients, and costs."""
    recipes = models.recipes
    products = models.products

    query = (
        sa.select(
            products.c.name.label("product_name"),
            products.c.price.label("menu_price_cents"),
            recipes.c.version.label("recipe_version"),
            recipes.c.cost_per_serving.label("serving_cost"),
        )
        .select_from(recipes.join(products, products.c.id == recipes.c.product_id))
        .where(
            recipes.c.organization_id == organization_id,
            recipes.c.status == "active",
        )
    )

    if search_term:
        query = query.where(sa.func.lower(products.c.name).like(f"%{search_term.strip().lower()}%"))

    rows = session.execute(query.order_by(products.c.name.asc()).limit(20)).all()

    recipe_items = []
    for r in rows:
        price = (int(r.menu_price_cents or 0)) / 100
        cost = float(r.serving_cost or 0.0)
        margin = ((price - cost) / price * 100) if price > 0 else 0.0
        recipe_items.append(
            {
                "producto": str(r.product_name),
                "precio_venta": f"${price:,.2f}",
                "costo_porcion": f"${cost:,.2f}",
                "margen": f"{margin:.1f}%",
                "version": int(r.recipe_version or 1),
            }
        )

    return {
        "total": len(recipe_items),
        "recetas": recipe_items,
    }


def tool_get_suggested_purchases(
    session: Session,
    organization_id: str,
    branch_name_or_id: str | None = None,
    days_ahead: int = 7,
) -> dict[str, Any]:
    """Calculate projected purchase orders grouped by supplier."""
    branch_id, branch_label = _resolve_branch(session, organization_id, branch_name_or_id)
    purchases = calculate_suggested_purchases(session, branch_id=branch_id, days_ahead=days_ahead)

    return {
        "branch_name": branch_label,
        "dias_proyeccion": days_ahead,
        "ordenes_sugeridas": purchases,
        "total_proveedores": len(purchases),
    }


# ---------------------------------------------------------------------------
# Dispatcher Central de Herramientas
# ---------------------------------------------------------------------------

def dispatch_copilot_tool(
    session: Session,
    organization_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    actor_id: str = "copilot-admin",
) -> dict[str, Any]:
    """Dispatch copilot tool execution securely."""
    if tool_name == "get_inventory_stock_and_thresholds":
        return tool_get_inventory_thresholds_and_stock(
            session=session,
            organization_id=organization_id,
            branch_name_or_id=arguments.get("branch_name_or_id"),
            search_term=arguments.get("search_term"),
        )
    elif tool_name == "get_cash_status":
        return tool_get_cash_status(
            session=session,
            organization_id=organization_id,
            branch_name_or_id=arguments.get("branch_name_or_id"),
        )
    elif tool_name == "get_sales_performance":
        return tool_get_sales_performance(
            session=session,
            organization_id=organization_id,
            branch_name_or_id=arguments.get("branch_name_or_id"),
            days=int(arguments.get("days", 1)),
        )
    elif tool_name == "get_recipes_list":
        return tool_get_recipes_list(
            session=session,
            organization_id=organization_id,
            search_term=arguments.get("search_term"),
        )
    elif tool_name == "get_suggested_purchases":
        return tool_get_suggested_purchases(
            session=session,
            organization_id=organization_id,
            branch_name_or_id=arguments.get("branch_name_or_id"),
            days_ahead=int(arguments.get("days_ahead", 7)),
        )
    else:
        return {"error": f"Herramienta desconocida: {tool_name}"}

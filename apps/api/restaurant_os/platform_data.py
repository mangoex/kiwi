from typing import Any

# ruff: noqa: E501, E402
import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID


def list_organizations(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.organizations.c.id,
            models.organizations.c.name,
            models.organizations.c.status,
            models.organizations.c.created_at,
        ).order_by(models.organizations.c.name)
    ).mappings()

    return [dict(row) for row in rows]


def list_branches(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.branches.c.id,
            models.branches.c.name,
            models.branches.c.code,
            models.branches.c.timezone,
            models.branches.c.status,
            models.legal_entities.c.name.label("legal_entity_name"),
            models.warehouses.c.name.label("warehouse_name"),
        )
        .select_from(
            models.branches.join(
                models.legal_entities,
                models.branches.c.legal_entity_id == models.legal_entities.c.id,
            ).join(models.warehouses, models.branches.c.id == models.warehouses.c.branch_id)
        )
        .order_by(models.branches.c.name)
    ).mappings()

    return [dict(row) for row in rows]


def list_roles(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.roles.c.id,
            models.roles.c.name,
            models.roles.c.scope,
            models.roles.c.created_at,
        ).order_by(models.roles.c.name)
    ).mappings()

    roles_by_id = {row["id"]: {**dict(row), "permissions": []} for row in rows}
    if not roles_by_id:
        return []

    permission_rows = session.execute(
        sa.select(
            models.role_permissions.c.role_id,
            models.permissions.c.code,
        )
        .select_from(
            models.role_permissions.join(
                models.permissions,
                models.role_permissions.c.permission_id == models.permissions.c.id,
            )
        )
        .where(models.role_permissions.c.role_id.in_(roles_by_id.keys()))
        .order_by(models.permissions.c.code)
    ).mappings()
    for row in permission_rows:
        roles_by_id[row["role_id"]]["permissions"].append(row["code"])

    return list(roles_by_id.values())


def list_users(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.users.c.id,
            models.users.c.email,
            models.users.c.display_name,
            models.users.c.status,
            models.users.c.created_at,
        ).order_by(models.users.c.display_name)
    ).mappings()
    users_by_id = {row["id"]: {**dict(row), "roles": []} for row in rows}
    if not users_by_id:
        return []

    role_rows = session.execute(
        sa.select(
            models.user_roles.c.user_id,
            models.user_roles.c.branch_id,
            models.roles.c.id.label("role_id"),
            models.roles.c.name.label("role_name"),
            models.roles.c.scope,
            models.branches.c.name.label("branch_name"),
        )
        .select_from(
            models.user_roles.join(
                models.roles,
                models.user_roles.c.role_id == models.roles.c.id,
            ).outerjoin(models.branches, models.user_roles.c.branch_id == models.branches.c.id)
        )
        .where(models.user_roles.c.user_id.in_(users_by_id.keys()))
        .order_by(models.roles.c.name)
    ).mappings()
    for row in role_rows:
        users_by_id[row["user_id"]]["roles"].append(
            {
                "role_id": row["role_id"],
                "role_name": row["role_name"],
                "scope": row["scope"],
                "branch_id": row["branch_id"],
                "branch_name": row["branch_name"],
            }
        )

    return list(users_by_id.values())


def list_catalog_products(session: Session, branch_id: str | None = None) -> list[dict[str, Any]]:
    active_price = (
        sa.select(
            models.price_versions.c.product_id,
            models.price_versions.c.price_cents,
            models.price_versions.c.currency,
        )
        .where(models.price_versions.c.valid_to.is_(None))
        .subquery()
    )
    
    query = sa.select(
        models.products.c.id,
        models.products.c.name,
        models.products.c.sku,
        models.products.c.description,
        models.products.c.station,
        models.products.c.status,
        models.products.c.image_url,
        models.product_categories.c.name.label("category_name"),
        active_price.c.price_cents,
        active_price.c.currency,
    )
    
    if branch_id:
        query = query.add_columns(
            sa.func.coalesce(models.branch_product_availability.c.is_available, True).label("is_available")
        ).select_from(
            models.products.join(
                models.product_categories,
                models.products.c.category_id == models.product_categories.c.id,
            )
            .join(active_price, models.products.c.id == active_price.c.product_id)
            .outerjoin(
                models.branch_product_availability,
                sa.and_(
                    models.products.c.id == models.branch_product_availability.c.product_id,
                    models.branch_product_availability.c.branch_id == branch_id
                )
            )
        ).where(
            sa.func.coalesce(models.branch_product_availability.c.is_available, True).is_(True)
        )
    else:
        query = query.add_columns(
            sa.literal(True).label("is_available")
        ).select_from(
            models.products.join(
                models.product_categories,
                models.products.c.category_id == models.product_categories.c.id,
            )
            .join(active_price, models.products.c.id == active_price.c.product_id)
        )

    rows = session.execute(query.order_by(models.product_categories.c.name, models.products.c.name)).mappings()

    return [dict(row) for row in rows]


def list_inventory_stock(session: Session) -> list[dict[str, Any]]:
    stock = (
        sa.select(
            models.inventory_movements.c.item_id,
            models.inventory_movements.c.warehouse_id,
            sa.func.sum(models.inventory_movements.c.quantity_delta).label("quantity_on_hand"),
            sa.func.max(models.inventory_movements.c.created_at).label("last_movement_at"),
        )
        .group_by(models.inventory_movements.c.item_id, models.inventory_movements.c.warehouse_id)
        .subquery()
    )
    rows = session.execute(
        sa.select(
            models.inventory_items.c.id,
            models.inventory_items.c.name,
            models.inventory_items.c.sku,
            models.inventory_items.c.item_type,
            models.inventory_units.c.code.label("unit_code"),
            models.inventory_units.c.name.label("unit_name"),
            models.warehouses.c.id.label("warehouse_id"),
            models.warehouses.c.name.label("warehouse_name"),
            models.branches.c.name.label("branch_name"),
            stock.c.quantity_on_hand,
            stock.c.last_movement_at,
        )
        .select_from(
            models.inventory_items.join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
            )
            .outerjoin(stock, models.inventory_items.c.id == stock.c.item_id)
            .outerjoin(models.warehouses, stock.c.warehouse_id == models.warehouses.c.id)
            .outerjoin(models.branches, models.warehouses.c.branch_id == models.branches.c.id)
        )
        .where(models.inventory_items.c.status == "active")
        .order_by(models.inventory_items.c.name)
    ).mappings()

    return [
        {
            **dict(row),
            "quantity_on_hand": int(row["quantity_on_hand"] or 0),
        }
        for row in rows
    ]


def list_inventory_kardex(session: Session, item_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        sa.select(
            models.inventory_movements.c.id,
            models.inventory_movements.c.item_id,
            models.inventory_items.c.name.label("item_name"),
            models.inventory_items.c.sku,
            models.inventory_movements.c.movement_type,
            models.inventory_movements.c.quantity_delta,
            models.inventory_units.c.code.label("unit_code"),
            models.warehouses.c.name.label("warehouse_name"),
            models.inventory_movements.c.reason,
            models.inventory_movements.c.source_type,
            models.inventory_movements.c.created_at,
        )
        .select_from(
            models.inventory_movements.join(
                models.inventory_items,
                models.inventory_movements.c.item_id == models.inventory_items.c.id,
            )
            .join(
                models.inventory_units,
                models.inventory_movements.c.unit_id == models.inventory_units.c.id,
            )
            .join(
                models.warehouses,
                models.inventory_movements.c.warehouse_id == models.warehouses.c.id,
            )
        )
        .order_by(
            models.inventory_movements.c.created_at.desc(),
            models.inventory_movements.c.id.desc(),
        )
        .limit(80)
    )
    if item_id:
        query = query.where(models.inventory_movements.c.item_id == item_id)

    return [dict(row) for row in session.execute(query).mappings()]


def list_active_recipes(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.recipes.c.id,
            models.recipes.c.product_id,
            models.products.c.name.label("product_name"),
            models.products.c.sku.label("product_sku"),
            models.recipes.c.version,
            models.recipes.c.status,
            models.recipes.c.yield_quantity,
            models.inventory_units.c.code.label("yield_unit_code"),
            models.recipes.c.created_at,
        )
        .select_from(
            models.recipes.join(
                models.products,
                models.recipes.c.product_id == models.products.c.id,
            ).join(
                models.inventory_units,
                models.recipes.c.yield_unit_id == models.inventory_units.c.id,
            )
        )
        .where(models.recipes.c.status == "active")
        .order_by(models.products.c.name)
    ).mappings()
    recipes_by_id = {row["id"]: {**dict(row), "components": []} for row in rows}
    if not recipes_by_id:
        return []

    component_rows = session.execute(
        sa.select(
            models.recipe_components.c.recipe_id,
            models.inventory_items.c.name.label("item_name"),
            models.inventory_items.c.sku.label("item_sku"),
            models.recipe_components.c.quantity_base_units,
            models.inventory_units.c.code.label("unit_code"),
        )
        .select_from(
            models.recipe_components.join(
                models.inventory_items,
                models.recipe_components.c.item_id == models.inventory_items.c.id,
            ).join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
            )
        )
        .where(models.recipe_components.c.recipe_id.in_(recipes_by_id.keys()))
        .order_by(models.inventory_items.c.name)
    ).mappings()
    for row in component_rows:
        recipes_by_id[row["recipe_id"]]["components"].append(
            {
                "item_name": row["item_name"],
                "item_sku": row["item_sku"],
                "quantity_base_units": row["quantity_base_units"],
                "unit_code": row["unit_code"],
            }
        )

    return list(recipes_by_id.values())


def bootstrap_status(session: Session) -> dict[str, Any]:
    counts = {
        "organizations": _count(session, models.organizations),
        "legal_entities": _count(session, models.legal_entities),
        "branches": _count(session, models.branches),
        "warehouses": _count(session, models.warehouses),
        "users": _count(session, models.users),
        "roles": _count(session, models.roles),
        "audit_events": _count(session, models.audit_events),
        "product_categories": _count_if_exists(session, models.product_categories),
        "products": _count_if_exists(session, models.products),
        "price_versions": _count_if_exists(session, models.price_versions),
        "cash_shifts": _count_if_exists(session, models.cash_shifts),
        "orders": _count_if_exists(session, models.orders),
        "production_tasks": _count_if_exists(session, models.production_tasks),
        "payments": _count_if_exists(session, models.payments),
        "cash_shift_cuts": _count_if_exists(session, models.cash_shift_cuts),
        "print_jobs": _count_if_exists(session, models.print_jobs),
        "sync_commands": _count_if_exists(session, models.sync_commands),
        "sync_events": _count_if_exists(session, models.sync_events),
        "inventory_units": _count_if_exists(session, models.inventory_units),
        "inventory_items": _count_if_exists(session, models.inventory_items),
        "recipes": _count_if_exists(session, models.recipes),
        "inventory_movements": _count_if_exists(session, models.inventory_movements),
    }
    organizations = list_organizations(session)
    branches = list_branches(session)

    return {
        "status": "ok" if counts["organizations"] and counts["branches"] else "needs_seed",
        "counts": counts,
        "primary_organization": organizations[0] if organizations else None,
        "primary_branch": branches[0] if branches else None,
    }


def _count(session: Session, table: sa.Table) -> int:
    return int(session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())


def _count_if_exists(session: Session, table: sa.Table) -> int:
    try:
        return _count(session, table)
    except sa.exc.SQLAlchemyError:
        return 0

def list_permissions(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(models.permissions).order_by(models.permissions.c.code)
    ).fetchall()
    return [
        {
            "id": row.id,
            "code": row.code,
            "description": row.description,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def list_role_permissions(session: Session, role_id: str) -> list[str]:
    rows = session.execute(
        sa.select(models.role_permissions.c.permission_id)
        .where(models.role_permissions.c.role_id == role_id)
    ).fetchall()
    return [row.permission_id for row in rows]


def list_warehouses(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(models.warehouses).where(
            models.warehouses.c.organization_id == ORGANIZATION_ID,
            models.warehouses.c.status == "active",
        )
    ).fetchall()
    return [
        {
            "id": row.id,
            "branch_id": row.branch_id,
            "name": row.name,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

def list_inventory_units(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(models.inventory_units).where(
            models.inventory_units.c.organization_id == ORGANIZATION_ID
        ).order_by(models.inventory_units.c.name)
    ).fetchall()
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "precision_scale": row.precision_scale,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

def list_inventory_items(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.inventory_items,
            models.inventory_units.c.name.label("unit_name"),
            models.inventory_units.c.code.label("unit_code")
        )
        .select_from(
            models.inventory_items.join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id
            )
        )
        .where(models.inventory_items.c.organization_id == ORGANIZATION_ID)
        .order_by(models.inventory_items.c.name)
    ).fetchall()
    return [
        {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "base_unit_id": row.base_unit_id,
            "unit_name": row.unit_name,
            "unit_code": row.unit_code,
            "item_type": row.item_type,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

def list_categories(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(models.product_categories).where(
            models.product_categories.c.organization_id == ORGANIZATION_ID
        ).order_by(models.product_categories.c.display_order, models.product_categories.c.name)
    ).fetchall()
    return [
        {
            "id": row.id,
            "name": row.name,
            "display_order": row.display_order,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

def get_product_recipe(session: Session, product_id: str) -> dict[str, Any] | None:
    recipe = session.execute(
        sa.select(models.recipes).where(
            models.recipes.c.product_id == product_id,
            models.recipes.c.status == "active"
        )
    ).first()
    if not recipe:
        return None
        
    components = session.execute(
        sa.select(
            models.recipe_components,
            models.inventory_items.c.name.label("item_name"),
            models.inventory_items.c.sku.label("item_sku"),
            models.inventory_units.c.code.label("unit_code")
        )
        .select_from(
            models.recipe_components
            .join(models.inventory_items, models.recipe_components.c.item_id == models.inventory_items.c.id)
            .join(models.inventory_units, models.inventory_items.c.base_unit_id == models.inventory_units.c.id)
        )
        .where(models.recipe_components.c.recipe_id == recipe.id)
    ).fetchall()
    
    return {
        "id": recipe.id,
        "version": recipe.version,
        "yield_quantity": recipe.yield_quantity,
        "yield_unit_id": recipe.yield_unit_id,
        "components": [
            {
                "item_id": c.item_id,
                "item_name": c.item_name,
                "item_sku": c.item_sku,
                "unit_code": c.unit_code,
                "quantity": c.quantity_base_units,
            } for c in components
        ]
    }

from datetime import datetime, timezone, timedelta
def get_dashboard_overview(session: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    
    # Total Revenue (Earnings)
    revenue_result = session.execute(
        sa.select(sa.func.sum(models.orders.c.total_cents))
        .where(models.orders.c.status.in_(["ACCEPTED", "PREPARING", "READY", "COMPLETED"]))
    ).scalar()
    total_revenue = int(revenue_result or 0)
    
    # Total Orders
    orders_result = session.execute(
        sa.select(sa.func.count(models.orders.c.id))
        .where(models.orders.c.status.in_(["ACCEPTED", "PREPARING", "READY", "COMPLETED"]))
    ).scalar()
    total_orders = int(orders_result or 0)
    
    # Total Products Active
    products_result = session.execute(
        sa.select(sa.func.count(models.products.c.id))
        .where(models.products.c.status == "active")
    ).scalar()
    total_products = int(products_result or 0)
    
    # Recent Transactions
    recent_transactions_query = (
        sa.select(
            models.payments.c.id,
            models.payments.c.amount_cents,
            models.payments.c.status,
            models.payments.c.created_at,
            models.orders.c.folio,
        )
        .select_from(
            models.payments.join(models.orders, models.payments.c.order_id == models.orders.c.id)
        )
        .order_by(models.payments.c.created_at.desc())
        .limit(5)
    )
    transactions = session.execute(recent_transactions_query).mappings()
    recent_transactions = [
        {
            "id": t["id"],
            "amount_cents": t["amount_cents"],
            "status": t["status"],
            "created_at": t["created_at"].isoformat(),
            "folio": t["folio"],
        }
        for t in transactions
    ]
    
    # Monthly Purchase Activity (Sales per day for the last 30 days)
    # We will aggregate by date. Note: date truncation is DB specific, we'll do simple extraction in python for now.
    sales_last_30_query = (
        sa.select(
            models.orders.c.created_at,
            models.orders.c.total_cents,
            models.orders.c.status,
        )
        .where(models.orders.c.created_at >= month_ago)
    )
    sales = session.execute(sales_last_30_query).mappings()
    
    # Group by day
    activity_by_day = {}
    for s in sales:
        day_str = s["created_at"].strftime("%b %d")
        if day_str not in activity_by_day:
            activity_by_day[day_str] = {"completed": 0, "pending": 0}
            
        if s["status"] in ["ACCEPTED", "PREPARING", "READY", "COMPLETED"]:
            activity_by_day[day_str]["completed"] += 1
        else:
            activity_by_day[day_str]["pending"] += 1
            
    # Format for charts
    activity_chart = [
        {"day": k, "completed": v["completed"], "pending": v["pending"]}
        for k, v in activity_by_day.items()
    ]
    
    return {
        "total_revenue_cents": total_revenue,
        "total_orders": total_orders,
        "total_products": total_products,
        "recent_transactions": recent_transactions,
        "activity_chart": activity_chart[-15:] # take last 15 days if too many
    }

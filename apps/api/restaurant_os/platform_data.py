from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models


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


def list_catalog_products(session: Session) -> list[dict[str, Any]]:
    active_price = (
        sa.select(
            models.price_versions.c.product_id,
            models.price_versions.c.price_cents,
            models.price_versions.c.currency,
        )
        .where(models.price_versions.c.valid_to.is_(None))
        .subquery()
    )
    rows = session.execute(
        sa.select(
            models.products.c.id,
            models.products.c.name,
            models.products.c.sku,
            models.products.c.station,
            models.products.c.status,
            models.product_categories.c.name.label("category_name"),
            active_price.c.price_cents,
            active_price.c.currency,
            models.branch_product_availability.c.is_available,
        )
        .select_from(
            models.products.join(
                models.product_categories,
                models.products.c.category_id == models.product_categories.c.id,
            )
            .join(active_price, models.products.c.id == active_price.c.product_id)
            .join(
                models.branch_product_availability,
                models.products.c.id == models.branch_product_availability.c.product_id,
            )
        )
        .order_by(models.product_categories.c.name, models.products.c.name)
    ).mappings()

    return [dict(row) for row in rows]


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

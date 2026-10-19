"""Administrative inventory reads, independent from the operational workspace."""

from __future__ import annotations

import logging
from decimal import Decimal
from time import perf_counter
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _actor_has_organization_scope,
    _compatible_permission_codes,
    _now,
    _record_authorization_denied,
    _workspace_role_ids,
    require_permission,
)

logger = logging.getLogger(__name__)
RESERVATIONS = ("SALE_RESERVATION", "RESERVATION_RELEASE")


def inventory_query_capabilities(session: Session, actor: str) -> dict[str, Any]:
    organization_read = _actor_has_organization_scope(session, actor, "inventory.read")
    branches = models.branches
    warehouses = models.warehouses
    query = (
        sa.select(
            branches.c.id,
            branches.c.name,
            branches.c.timezone,
            warehouses.c.name.label("warehouse_name"),
        )
        .select_from(
            branches.outerjoin(
                warehouses,
                sa.and_(
                    warehouses.c.branch_id == branches.c.id,
                    warehouses.c.organization_id == ORGANIZATION_ID,
                    warehouses.c.status == "active",
                ),
            )
        )
        .where(branches.c.organization_id == ORGANIZATION_ID, branches.c.status == "active")
    )
    if not organization_read:
        assignments = list(
            session.execute(
                sa.select(
                    models.user_roles.c.role_id,
                    models.user_roles.c.branch_id,
                )
                .select_from(
                    models.user_roles.join(models.roles)
                    .join(models.role_permissions)
                    .join(models.permissions)
                )
                .where(
                    models.user_roles.c.user_id == actor,
                    models.roles.c.organization_id == ORGANIZATION_ID,
                    models.permissions.c.code.in_(_compatible_permission_codes("inventory.read")),
                )
            ).mappings()
        )
        mobile_roles = _workspace_role_ids(session, actor)
        if not any(str(row["role_id"]) in mobile_roles for row in assignments):
            query = query.where(
                branches.c.id.in_([row["branch_id"] for row in assignments if row["branch_id"]])
            )
    return {
        "organization_read": organization_read,
        "branches": [
            dict(row)
            for row in session.execute(query.order_by(branches.c.name, branches.c.id)).mappings()
        ],
    }


def inventory_overview(
    session: Session,
    actor: str,
    *,
    scope: str,
    branch_id: str | None,
    q: str = "",
    availability: str = "all",
    unit_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    started = perf_counter()
    # This endpoint owns a fresh session; select isolation before any SQL/auth projection.
    if session.get_bind().dialect.name == "postgresql":
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    capabilities = inventory_query_capabilities(session, actor)
    if scope == "organization":
        if not capabilities["organization_read"]:
            require_permission(session, actor, "inventory.read", branch_id)
            _record_authorization_denied(
                session, actor, "inventory.read", None, "organization_inventory_required"
            )
            raise AuthorizationError(
                "permission_denied", "Organization inventory access is required"
            )
        require_permission(session, actor, "inventory.read", None)
        branches = capabilities["branches"]
    else:
        # Preserve canonical authorization denial audit and never probe an unrelated destination.
        branches = [row for row in capabilities["branches"] if row["id"] == branch_id]
        if not branches:
            require_permission(session, actor, "inventory.read", None)
            _record_authorization_denied(
                session, actor, "inventory.read", None, "invalid_inventory_destination"
            )
            raise AuthorizationError("permission_denied", "Inventory destination is not authorized")
        require_permission(session, actor, "inventory.read", branch_id)
    if session.get_bind().dialect.name == "postgresql":
        session.execute(sa.text("SET TRANSACTION READ ONLY"))
    ids = [row["id"] for row in branches]
    b, w, i, u, m = (
        models.branches,
        models.warehouses,
        models.inventory_items,
        models.inventory_units,
        models.inventory_movements,
    )
    warehouses = list(
        session.execute(
            sa.select(w.c.branch_id).where(
                w.c.organization_id == ORGANIZATION_ID,
                w.c.status == "active",
                w.c.branch_id.in_(ids),
            )
        ).scalars()
    )
    if sorted(warehouses) != sorted(ids):
        raise BusinessError(
            "inventory_warehouse_invalid",
            "An inventory destination has no valid canonical warehouse",
        )
    physical = sa.func.coalesce(
        sa.func.sum(sa.case((m.c.movement_type.not_in(RESERVATIONS), m.c.quantity_delta), else_=0)),
        0,
    )
    available = sa.func.coalesce(sa.func.sum(m.c.quantity_delta), 0)
    aggregate = (
        sa.select(
            m.c.item_id,
            m.c.branch_id,
            m.c.warehouse_id,
            physical.label("physical"),
            available.label("available"),
            sa.func.max(m.c.created_at).label("last_movement_at"),
        )
        .where(m.c.organization_id == ORGANIZATION_ID, m.c.branch_id.in_(ids))
        .group_by(m.c.item_id, m.c.branch_id, m.c.warehouse_id)
        .subquery()
    )
    pairs = (
        i.join(u, sa.and_(u.c.id == i.c.base_unit_id, u.c.organization_id == ORGANIZATION_ID))
        .join(
            b,
            sa.and_(
                b.c.id.in_(ids),
                b.c.organization_id == ORGANIZATION_ID,
                sa.or_(i.c.catalog_scope == "organization", i.c.source_branch_id == b.c.id),
            ),
        )
        .join(
            w,
            sa.and_(
                w.c.branch_id == b.c.id,
                w.c.organization_id == ORGANIZATION_ID,
                w.c.status == "active",
            ),
        )
        .outerjoin(
            aggregate,
            sa.and_(
                aggregate.c.item_id == i.c.id,
                aggregate.c.branch_id == b.c.id,
                aggregate.c.warehouse_id == w.c.id,
            ),
        )
    )
    physical_qty = sa.func.coalesce(aggregate.c.physical, 0)
    available_qty = sa.func.coalesce(aggregate.c.available, 0)
    query = (
        sa.select(
            i.c.id.label("item_id"),
            i.c.name.label("item_name"),
            i.c.sku,
            i.c.item_type,
            u.c.id.label("unit_id"),
            u.c.code.label("unit_code"),
            b.c.id.label("branch_id"),
            b.c.name.label("branch_name"),
            b.c.timezone,
            w.c.id.label("warehouse_id"),
            w.c.name.label("warehouse_name"),
            physical_qty.label("physical_quantity"),
            (physical_qty - available_qty).label("reserved_quantity"),
            available_qty.label("available_quantity"),
            aggregate.c.last_movement_at,
        )
        .select_from(pairs)
        .where(i.c.organization_id == ORGANIZATION_ID, i.c.status == "active")
    )
    if q.strip():
        literal = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            sa.or_(
                i.c.name.ilike(f"%{literal}%", escape="\\"),
                i.c.sku.ilike(f"%{literal}%", escape="\\"),
            )
        )
    if unit_id:
        query = query.where(u.c.id == unit_id)
    if availability != "all":
        query = query.where(
            {
                "positive": available_qty > 0,
                "zero": available_qty == 0,
                "negative": available_qty < 0,
            }[availability]
        )
    filtered = query.subquery()
    counts = (
        session.execute(
            sa.select(
                sa.func.count().label("total"),
                *[
                    sa.func.coalesce(sa.func.sum(sa.case((condition, 1), else_=0)), 0).label(key)
                    for key, condition in [
                        ("positive", filtered.c.available_quantity > 0),
                        ("zero", filtered.c.available_quantity == 0),
                        ("negative", filtered.c.available_quantity < 0),
                    ]
                ],
            ).select_from(filtered)
        )
        .mappings()
        .one()
    )
    rows = session.execute(
        query.order_by(i.c.name, i.c.id, b.c.id, w.c.id).limit(limit).offset(offset)
    ).mappings()
    items = []
    for row in rows:
        item = dict(row)
        for key in ("physical_quantity", "reserved_quantity", "available_quantity"):
            item[key] = format(Decimal(str(item[key])).quantize(Decimal("0.000001")), "f")
        item["reservation_inconsistent"] = Decimal(item["reserved_quantity"]) < 0
        items.append(item)
    logger.info(
        "inventory.overview",
        extra={
            "metric": "inventory.overview",
            "scope": scope,
            "result": "ok",
            "duration_ms": int((perf_counter() - started) * 1000),
            "branch_count": len(ids),
            "row_count": len(items),
        },
    )
    return {
        "scope": {"kind": scope, "branch_id": branch_id},
        "as_of": _now(),
        "items": items,
        "total_rows": int(counts["total"]),
        "limit": limit,
        "offset": offset,
        "counts": {key: int(counts[key]) for key in ("positive", "zero", "negative")},
    }

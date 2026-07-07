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


def bootstrap_status(session: Session) -> dict[str, Any]:
    counts = {
        "organizations": _count(session, models.organizations),
        "legal_entities": _count(session, models.legal_entities),
        "branches": _count(session, models.branches),
        "warehouses": _count(session, models.warehouses),
        "users": _count(session, models.users),
        "roles": _count(session, models.roles),
        "audit_events": _count(session, models.audit_events),
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


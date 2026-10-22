"""Delivery ledger projections from immutable payment and correction snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.delivery_fee import _branch, _invalid
from restaurant_os.operations import ORGANIZATION_ID, require_permission


def report(
    session: Session,
    actor: str,
    branch_id: str,
    start: datetime,
    end: datetime,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    from restaurant_os.financial_reads import require_financial_read

    require_financial_read(session, actor, branch_id, ("sales",))
    require_permission(session, actor, "reports.sales.read", branch_id)
    _branch(session, branch_id)
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or not start < end
        or (end - start).days > 93
        or not 1 <= limit <= 100
        or not 0 <= offset <= 100000
    ):
        raise _invalid("Delivery report requires bounded UTC dates and pagination")
    p, s, o = models.payments, models.delivery_sale_snapshots, models.orders
    source = s.join(p, s.c.payment_id == p.c.id).join(o, o.c.id == p.c.order_id)
    sales = (
        sa.select(
            s.c.id.label("id"),
            p.c.confirmed_at.label("at"),
            o.c.folio,
            o.c.id.label("order_id"),
            o.c.channel,
            sa.literal("PAYMENT").label("kind"),
            s.c.snapshot["state"].as_string().label("state"),
            s.c.snapshot["charged_cents"].as_integer().label("gross_cents"),
            s.c.snapshot["net_cents"].as_integer().label("net_cents"),
            s.c.snapshot["tax_cents"].as_integer().label("tax_cents"),
        )
        .select_from(source)
        .where(
            p.c.organization_id == ORGANIZATION_ID,
            p.c.branch_id == branch_id,
            p.c.status == "CONFIRMED",
            p.c.confirmed_at >= start,
            p.c.confirmed_at < end,
        )
    )
    c = models.order_corrections
    before = c.c.before_snapshot["delivery_charge"]
    after = c.c.after_snapshot["delivery_charge"]
    corrections = (
        sa.select(
            c.c.id.label("id"),
            c.c.applied_at.label("at"),
            o.c.folio,
            o.c.id.label("order_id"),
            o.c.channel,
            sa.literal("CORRECTION").label("kind"),
            after["state"].as_string().label("state"),
            (after["charged_cents"].as_integer() - before["charged_cents"].as_integer()).label(
                "gross_cents"
            ),
            (after["net_cents"].as_integer() - before["net_cents"].as_integer()).label("net_cents"),
            (after["tax_cents"].as_integer() - before["tax_cents"].as_integer()).label("tax_cents"),
        )
        .select_from(c.join(o, o.c.id == c.c.order_id))
        .where(
            c.c.organization_id == ORGANIZATION_ID,
            c.c.branch_id == branch_id,
            c.c.applied_at >= start,
            c.c.applied_at < end,
            after["charged_cents"].as_integer().is_not(None),
        )
    )
    ledger = sa.union_all(sales, corrections).subquery()
    totals = (
        session.execute(
            sa.select(
                sa.func.count().label("entry_count"),
                sa.func.coalesce(sa.func.sum(ledger.c.gross_cents), 0).label("gross_cents"),
                sa.func.coalesce(sa.func.sum(ledger.c.net_cents), 0).label("net_cents"),
                sa.func.coalesce(sa.func.sum(ledger.c.tax_cents), 0).label("tax_cents"),
            )
        )
        .mappings()
        .one()
    )
    rows = (
        session.execute(
            sa.select(ledger).order_by(ledger.c.at, ledger.c.id).limit(limit + 1).offset(offset)
        )
        .mappings()
        .all()
    )
    missing = session.scalar(
        sa.select(sa.func.count())
        .select_from(p.join(o, o.c.id == p.c.order_id))
        .where(
            p.c.organization_id == ORGANIZATION_ID,
            p.c.branch_id == branch_id,
            p.c.status == "CONFIRMED",
            o.c.order_type == "delivery",
            p.c.confirmed_at >= start,
            p.c.confirmed_at < end,
            ~sa.exists(sa.select(s.c.id).where(s.c.payment_id == p.c.id)),
        )
    )
    return {
        "items": [dict(row) for row in rows[:limit]],
        "summary": dict(totals),
        "legacy_not_captured": missing,
        "has_more": len(rows) > limit,
        "next_offset": offset + limit if len(rows) > limit else None,
    }

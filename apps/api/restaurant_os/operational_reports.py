"""CC-D12 operational reporting from confirmed immutable sales snapshots."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import FinancialAuthority

Period = Literal["day", "week", "month"]


class RankedProductV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    position: int = Field(ge=1, le=10)
    name: str = Field(min_length=1)


class OperationalReportV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    branch_id: str
    period: Period
    start: datetime
    end: datetime
    timezone: str
    ticket_count: int = Field(ge=0)
    top_products: list[RankedProductV2] = Field(max_length=10)
    schema_version: Literal[2] = 2
    policy_version: int = Field(ge=1)
    projection: Literal["operational"] = "operational"


def calendar_bounds(anchor: date, period: Period, timezone_name: str) -> tuple[datetime, datetime]:
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ops.BusinessError("report_timezone_invalid", "Branch timezone is invalid") from exc
    start = anchor
    if period == "day":
        end = start + timedelta(days=1)
    elif period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=7)
    elif period == "month":
        start = anchor.replace(day=1)
        end = (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
    else:
        raise ops.BusinessError("report_period_invalid", "Use day, week or month")
    return (
        datetime.combine(start, time.min, zone).astimezone(timezone.utc),
        datetime.combine(end, time.min, zone).astimezone(timezone.utc),
    )


def operational_report(
    session: Session,
    actor: str,
    branch_id: str,
    period: Period,
    anchor: date,
) -> OperationalReportV2:
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    authority.require_operational_report(branch_id)
    revision = authority.policy_revision(branch_id)
    if revision is None:
        raise ops.BusinessError("cash_policy_not_active", "Branch policy is not active")
    zone = str(
        session.scalar(
            sa.select(models.branches.c.timezone).where(
                models.branches.c.id == branch_id,
                models.branches.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
    )
    start, end = calendar_bounds(anchor, period, zone)
    sales, lines = models.sales_operation_snapshots, models.sales_operation_line_snapshots
    scope = (
        sales.c.organization_id == ops.ORGANIZATION_ID,
        sales.c.branch_id == branch_id,
        sales.c.confirmed_at >= start,
        sales.c.confirmed_at < end,
    )
    tickets = int(
        session.scalar(
            sa.select(sa.func.count(sa.distinct(sales.c.order_id))).where(
                *scope,
            )
        )
        or 0
    )
    # Only identifiers/names/quantities are read internally. No money is loaded or redacted.
    ranked = (
        sa.select(
            lines.c.product_id,
            lines.c.product_name_snapshot,
            sa.func.sum(lines.c.quantity).over(partition_by=lines.c.product_id).label("units"),
            sa.func.row_number()
            .over(
                partition_by=lines.c.product_id,
                order_by=(sales.c.confirmed_at.desc(), sales.c.id.desc(), lines.c.id.desc()),
            )
            .label("name_rank"),
        )
        .select_from(lines.join(sales, lines.c.sales_operation_snapshot_id == sales.c.id))
        .where(
            *scope,
        )
        .subquery()
    )
    names = session.scalars(
        sa.select(ranked.c.product_name_snapshot)
        .where(
            ranked.c.name_rank == 1,
        )
        .order_by(ranked.c.units.desc(), ranked.c.product_id)
        .limit(10)
    ).all()
    return OperationalReportV2(
        branch_id=branch_id,
        period=period,
        start=start,
        end=end,
        timezone=zone,
        ticket_count=tickets,
        top_products=[
            RankedProductV2(position=index, name=name) for index, name in enumerate(names, 1)
        ],
        policy_version=revision,
    )

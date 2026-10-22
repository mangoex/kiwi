"""Closed financial payment/movement pages, independent from write permissions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.cash_views import CashPageV2
from restaurant_os.financial_authority import FinancialAuthority
from restaurant_os.financial_reads import read_branches, require_financial_read


class FinancialEntryV2(FinancialRecord):
    id: str
    organization_id: str
    branch_id: str
    cash_shift_id: str
    status: str
    amount_cents: int
    created_at: datetime
    projection: Literal["financial"] = "financial"
    schema_version: Literal[2] = 2
    policy_version: int


class PaymentFinancialV2(FinancialEntryV2):
    order_id: str
    method: str
    currency: str
    confirmed_at: datetime


class MovementFinancialV2(FinancialEntryV2):
    movement_type: str
    reason_code: str
    reason: str
    actor_user_id: str
    source_type: str | None
    source_id: str | None
    reversal_of_id: str | None
    compensates_movement_id: str | None
    concept_id: str | None
    concept_version_id: str | None
    reference: str | None


PAYMENT_FIELDS = (
    "id",
    "organization_id",
    "branch_id",
    "cash_shift_id",
    "status",
    "amount_cents",
    "created_at",
    "order_id",
    "method",
    "currency",
    "confirmed_at",
)
MOVEMENT_FIELDS = (
    "id",
    "organization_id",
    "branch_id",
    "cash_shift_id",
    "status",
    "amount_cents",
    "created_at",
    "movement_type",
    "reason_code",
    "reason",
    "actor_user_id",
    "source_type",
    "source_id",
    "reversal_of_id",
    "compensates_movement_id",
    "concept_id",
    "concept_version_id",
    "reference",
)


def financial_page(
    session: Session,
    actor: str,
    branch_id: str | None,
    kind: Literal["payments", "movements"],
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise ops.BusinessError("financial_page_invalid", "limit must be 1..100")
    dataset = "sales" if kind == "payments" else "cash.movements"
    require_financial_read(session, actor, branch_id, (dataset,), force=True)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    revisions = {
        branch: authority.policy_revision(branch)
        for branch in read_branches(
            session,
            branch_id,
        )
    }
    if any(revision is None for revision in revisions.values()):
        raise ops.BusinessError("cash_policy_not_active", "Branch policy is not active")
    table = models.payments if kind == "payments" else models.cash_movements
    fields = PAYMENT_FIELDS if kind == "payments" else MOVEMENT_FIELDS
    query = sa.select(*(table.c[field] for field in fields)).where(
        table.c.organization_id == ops.ORGANIZATION_ID,
        table.c.branch_id.in_(revisions),
    )
    if cursor:
        query = query.where(table.c.id > cursor)
    rows = list(session.execute(query.order_by(table.c.id).limit(limit + 1)).mappings())
    next_cursor = str(rows[limit - 1]["id"]) if len(rows) > limit else None
    payload = {
        "items": [
            dict(row, policy_version=revisions[str(row["branch_id"])]) for row in rows[:limit]
        ],
        "next_cursor": next_cursor,
    }
    schema = (
        CashPageV2[PaymentFinancialV2] if kind == "payments" else CashPageV2[MovementFinancialV2]
    )
    return schema.model_validate(payload).model_dump(mode="json")

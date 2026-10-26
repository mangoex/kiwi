"""Current financial read scope, shared by HTTP readers and domain projections."""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock

RECONCILIATION_DATASETS = (
    "reconciliation",
    "sales",
    "cash.shifts",
    "cash.cuts",
    "cash.movements",
    "expenses",
)


def read_branches(
    session: Session, branch_id: str | None, *, active_only: bool = False
) -> list[str]:
    """An omitted filter requests the whole organization, never an allowed subset."""
    query = sa.select(models.branches.c.id).where(
        models.branches.c.organization_id == ops.ORGANIZATION_ID,
    )
    if active_only:
        query = query.where(models.branches.c.status == "active")
    if branch_id is not None:
        query = query.where(models.branches.c.id == branch_id)
    result: sa.ScalarResult[str] = session.scalars(query.order_by(models.branches.c.id))
    branches = list(result)
    if branch_id is not None and branches != [branch_id]:
        deny()
    return branches


def require_financial_read(
    session: Session,
    actor: str | None,
    branch_id: str | None,
    datasets: Iterable[str],
    *,
    force: bool = False,
    active_only: bool = False,
) -> int | None:
    """Authorize before money queries; retain the transaction until DTO materialization.

    Legacy readers retain their original permission checks outside activated policy.
    A mixed consolidated read is protected in its entirety, not filtered after loading.
    """
    governance_lock(session, ops.ORGANIZATION_ID)
    if (
        not force
        and session.scalar(
            sa.select(models.blind_cash_policy_revisions.c.branch_id)
            .where(
                models.blind_cash_policy_revisions.c.organization_id == ops.ORGANIZATION_ID,
                models.blind_cash_policy_revisions.c.event == "activated",
            )
            .limit(1)
        )
        is None
    ):
        # The legacy domain retains its own scope contract before any activation.
        return None
    branches = read_branches(session, branch_id, active_only=active_only)
    if not force and not any(active_revision(session, branch) is not None for branch in branches):
        return None
    if actor is None:
        deny()
    assert actor is not None
    return FinancialAuthority(session, actor, ops.ORGANIZATION_ID).require_financial(
        [(branch, dataset) for branch in branches for dataset in datasets]
    )

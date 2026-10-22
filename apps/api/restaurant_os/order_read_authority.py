"""Server-derived, current authority for one order; never created by a lookup/reason."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock

ACTIVE_STATES = frozenset(
    {
        "PENDING",
        "ACCEPTED",
        "SENT_TO_PRODUCTION",
        "IN_PRODUCTION",
        "READY",
        "IN_DELIVERY",
        "DELIVERED",
    }
)


@dataclass(frozen=True)
class OrderReadContext:
    order_id: str
    branch_id: str
    order_version: int
    authorization_version: int
    policy_version: int
    source_kind: str
    source_id: str

    @property
    def financial(self) -> bool:
        return self.source_kind == "financial"


def _source(
    session: Session,
    actor: str,
    order: dict[str, Any],
) -> tuple[str, str] | None:
    branch, order_id = str(order["branch_id"]), str(order["id"])

    def allowed(permission: str) -> bool:
        return ops._actor_has_permission(session, actor, permission, branch)

    # Request creation alone does not authorize money. Only a still-approved,
    # version-bound action for its actual participant can supply this context.
    requests = models.order_reopen_requests
    approved = (
        session.execute(
            sa.select(
                requests.c.id,
                requests.c.requested_by_user_id,
                requests.c.decided_by_user_id,
            ).where(
                requests.c.organization_id == ops.ORGANIZATION_ID,
                requests.c.branch_id == branch,
                requests.c.order_id == order_id,
                requests.c.status == "APPROVED",
                requests.c.order_version_snapshot == order["version"],
                requests.c.order_status_snapshot == order["status"],
                sa.or_(
                    requests.c.requested_by_user_id == actor, requests.c.decided_by_user_id == actor
                ),
            )
        )
        .mappings()
        .first()
    )
    if approved and (
        (approved["decided_by_user_id"] == actor and allowed("orders.reopen.authorize"))
        or (approved["requested_by_user_id"] == actor and allowed("orders.reopen.request"))
    ):
        return "approved_reopen", str(approved["id"])

    if order["status"] not in ACTIVE_STATES:
        return None
    if order.get("cash_shift_id"):
        shift = session.scalar(
            sa.select(models.cash_shifts.c.status).where(
                models.cash_shifts.c.id == order["cash_shift_id"],
                models.cash_shifts.c.organization_id == ops.ORGANIZATION_ID,
                models.cash_shifts.c.branch_id == branch,
            )
        )
        if shift != "OPEN":
            return None
    if allowed("orders.create"):
        audits = models.audit_events
        acceptance = session.scalar(
            sa.select(audits.c.id)
            .where(
                audits.c.organization_id == ops.ORGANIZATION_ID,
                audits.c.branch_id == branch,
                audits.c.actor_user_id == actor,
                audits.c.entity_type == "order",
                audits.c.entity_id == order_id,
                audits.c.action == "order.accepted",
            )
            .order_by(audits.c.created_at, audits.c.id)
            .limit(1)
        )
        if acceptance:
            return "order_acceptance", str(acceptance)
        assignments = models.delivery_assignments
        assignment = session.scalar(
            sa.select(assignments.c.id)
            .where(
                assignments.c.organization_id == ops.ORGANIZATION_ID,
                assignments.c.branch_id == branch,
                assignments.c.order_id == order_id,
                assignments.c.assigned_by == actor,
                assignments.c.status == "ASSIGNED",
            )
            .with_for_update(read=True)
        )
        if assignment:
            return "delivery_assignment", str(assignment)
    if allowed("orders.amend"):
        amendments = models.order_amendments
        amendment = session.scalar(
            sa.select(amendments.c.id)
            .where(
                amendments.c.order_id == order_id,
                amendments.c.actor_user_id == actor,
                amendments.c.resulting_version == order["version"],
            )
            .order_by(amendments.c.sequence.desc())
            .limit(1)
        )
        if amendment:
            return "order_amendment", str(amendment)
    return None


def authorize_order_detail(
    session: Session,
    actor: str,
    order_id: str,
    *,
    expected_version: int | None = None,
    force: bool = False,
) -> OrderReadContext | None:
    governance_lock(session, ops.ORGANIZATION_ID)
    columns = ("id", "branch_id", "cash_shift_id", "status", "version")
    order = (
        session.execute(
            sa.select(*(models.orders.c[name] for name in columns)).where(
                models.orders.c.id == order_id,
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if order is None:
        intent = (
            session.execute(
                sa.select(
                    models.public_order_intents.c.id,
                    models.public_order_intents.c.branch_id,
                    models.public_order_intents.c.accepted_order_id,
                    models.public_order_intents.c.version,
                    models.public_order_intents.c.status,
                ).where(
                    models.public_order_intents.c.id == order_id,
                    models.public_order_intents.c.organization_id == ops.ORGANIZATION_ID,
                )
            )
            .mappings()
            .first()
        )
        if intent is None:
            raise ops.NotFoundError("order_not_found", "Order was not found")
        if intent["accepted_order_id"]:
            return authorize_order_detail(
                session,
                actor,
                str(intent["accepted_order_id"]),
                expected_version=expected_version,
                force=force,
            )
        order = intent
    branch = str(order["branch_id"])
    revision = active_revision(session, branch)
    if revision is None:
        if force:
            raise ops.BusinessError("cash_policy_not_active", "Branch policy is not active")
        return None
    policy = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    policy.policy_revision(branch)  # Current active human, organization and governance lock.
    if not ops._actor_has_permission(session, actor, "orders.read", branch):
        deny()
    # Canonical writers fence the branch, then lock a shift/order. Take that same
    # order; do not wait on a reopen request after holding the resource it applies to.
    session.execute(
        sa.select(models.branches.c.id)
        .where(
            models.branches.c.id == branch,
            models.branches.c.organization_id == ops.ORGANIZATION_ID,
        )
        .with_for_update(read=True)
    )
    if order.get("cash_shift_id"):
        session.execute(
            sa.select(models.cash_shifts.c.id)
            .where(
                models.cash_shifts.c.id == order["cash_shift_id"],
                models.cash_shifts.c.organization_id == ops.ORGANIZATION_ID,
                models.cash_shifts.c.branch_id == branch,
            )
            .with_for_update(read=True)
        )
    table = models.orders if "cash_shift_id" in order else models.public_order_intents
    locked = (
        session.execute(
            sa.select(*(table.c[name] for name in order.keys()))
            .where(
                table.c.id == order["id"],
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.branch_id == branch,
            )
            .with_for_update(read=True)
        )
        .mappings()
        .first()
    )
    if locked is None or locked.get("cash_shift_id") != order.get("cash_shift_id"):
        raise ops.BusinessError("order_version_conflict", "Order changed while acquiring authority")
    order = locked
    if order.get("accepted_order_id"):
        return authorize_order_detail(
            session,
            actor,
            str(order["accepted_order_id"]),
            expected_version=expected_version,
            force=force,
        )
    source: tuple[str, str] | None
    try:
        auth_version = policy.require_financial([(branch, "sales")])
        source = ("financial", branch)
    except ops.AuthorizationError:
        source = _source(session, actor, dict(order))
        if source is None:
            deny()
        auth_version = int(
            session.execute(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == actor,
                    models.users.c.organization_id == ops.ORGANIZATION_ID,
                )
            ).scalar_one()
        )
    assert source is not None
    # Do not expose a version conflict to an actor who has no context for this order.
    if expected_version is not None and int(order["version"]) != expected_version:
        raise ops.BusinessError("order_version_conflict", "Order version changed")
    return OrderReadContext(
        str(order["id"]),
        branch,
        int(order["version"]),
        auth_version,
        revision,
        *source,
    )


def audit_order_read(session: Session, actor: str, context: OrderReadContext) -> None:
    ops._audit(
        session,
        "order.detail_read",
        "order",
        context.order_id,
        {
            "source_kind": context.source_kind,
            "source_id": context.source_id,
            "order_version": context.order_version,
            "authorization_version": context.authorization_version,
            "policy_version": context.policy_version,
        },
        branch_id=context.branch_id,
        actor_user_id=actor,
    )

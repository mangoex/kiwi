"""Own acceptance/assignment receipts, independent of original financial snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import deny, governance_lock
from restaurant_os.order_command_receipts import require_receipt_access

Source = Literal["public_intent", "pending_order", "delivery_assignment"]


class OrderAcceptanceReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    action: Literal["order.accept", "delivery.assign"]
    source_kind: Source
    command_id: str
    id: str
    order_id: str
    branch_id: str
    status: Literal["ACCEPTED", "ASSIGNED"]
    accepted_at: datetime


def acceptance_digest(intent: str, version: int, driver: str | None) -> str:
    normalized = str(driver or "").strip() or None
    serialized = (
        f"{intent}:{version}"
        if normalized is None
        else json.dumps(
            {"driver_id": normalized, "expected_version": version, "intent_id": intent},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def _branch(session: Session, table: sa.Table, target: str) -> str:
    branch = session.scalar(
        sa.select(table.c.branch_id).where(
            table.c.organization_id == ops.ORGANIZATION_ID,
            table.c.id == target,
        )
    )
    if branch is None:
        raise ops.NotFoundError("order_not_found", "Order was not found")
    return str(branch)


def _finish(
    session: Session,
    actor: str,
    branch: str,
    revision: int,
    order: str,
    source: Source,
    fact: dict[str, Any],
    *,
    commit: bool,
) -> dict[str, Any]:
    if fact["actor_user_id"] != actor:
        deny()
    if require_receipt_access(session, actor, branch) != revision:
        raise ops.BusinessError("cash_authorization_changed", "Authority changed")
    assignment = source == "delivery_assignment"
    value = OrderAcceptanceReceiptV2(
        policy_version=revision,
        action="delivery.assign" if assignment else "order.accept",
        source_kind=source,
        command_id=fact["id"],
        id=fact["id"] if assignment else order,
        order_id=order,
        branch_id=branch,
        status="ASSIGNED" if assignment else "ACCEPTED",
        accepted_at=fact["created_at"],
    ).model_dump(mode="json")
    ops._audit(
        session,
        "order.acceptance.receipt_read",
        "order",
        order,
        {"source_kind": source, "command_id": fact["id"], "policy_version": revision},
        branch_id=branch,
        actor_user_id=actor,
    )
    if commit:
        session.commit()
        if require_receipt_access(session, actor, branch) != revision:
            raise ops.BusinessError("cash_authorization_changed", "Authority changed")
    return value


def _public_fact(session: Session, key: str) -> dict[str, Any] | None:
    t = models.public_order_intent_commands
    row = (
        session.execute(
            sa.select(
                t.c.id,
                t.c.intent_id,
                t.c.actor_user_id,
                t.c.request_hash,
                t.c.created_at,
                t.c.result["id"].as_string().label("order_id"),
            ).where(
                t.c.organization_id == ops.ORGANIZATION_ID,
                t.c.command_type == "accept",
                t.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def public_acceptance(
    session: Session,
    actor: str,
    intent: str,
    key: str,
    digest: str,
    execute: Callable[[bool], tuple[dict[str, Any], bool]],
    *,
    commit: bool,
) -> tuple[dict[str, Any], bool]:
    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        normalized = str(key or "").strip()
        if not 12 <= len(normalized) <= 160:
            raise ops.BusinessError("public_order_schema_invalid", "Idempotency-Key is invalid")
        # Serialize the organization-wide key before effects across branches.
        # Avoid entering the legacy rollback/snapshot recovery inside a caller's transaction.
        ops._acquire_idempotency_lock(
            session,
            "public-acceptance-receipt",
            ops.ORGANIZATION_ID + ":" + normalized,
        )
        branch = _branch(session, models.public_order_intents, intent)
        revision = require_receipt_access(session, actor, branch)
        if revision is None:
            result = execute(commit)
            if commit and require_receipt_access(session, actor, branch) is not None:
                raise ops.BusinessError("cash_authorization_changed", "Policy changed")
            return result
        fact = _public_fact(session, normalized)
        created = False
        if fact is None:
            # Match writer order only for a new effect; recovery is read authority.
            ops._require_order_write_fence(session, branch)
            fact = _public_fact(session, normalized)
        if fact is None:
            execute(False)
            created = True
            fact = _public_fact(session, normalized)
        if fact is None or not fact["order_id"]:
            raise ops.BusinessError("command_result_unavailable", "Acceptance is unavailable")
        if fact["actor_user_id"] != actor:
            deny()
        if fact["intent_id"] != intent or fact["request_hash"] != digest:
            raise ops.BusinessError("idempotency_conflict", "Acceptance intention changed")
        return _finish(
            session,
            actor,
            branch,
            revision,
            fact["order_id"],
            "public_intent",
            fact,
            commit=commit,
        ), created
    except Exception:
        if commit:
            session.rollback()
        raise


def _order_fact(
    session: Session,
    actor: str,
    branch: str,
    order: str,
    assignment: bool,
) -> dict[str, Any] | None:
    if assignment:
        t = models.delivery_assignments
        query = sa.select(
            t.c.id,
            t.c.driver_id,
            t.c.assigned_by.label("actor_user_id"),
            t.c.assigned_at.label("created_at"),
        ).where(t.c.order_id == order)
    else:
        t = models.audit_events
        query = (
            sa.select(t.c.id, t.c.actor_user_id, t.c.created_at)
            .where(
                t.c.entity_type == "order",
                t.c.entity_id == order,
                t.c.action == "order.accepted",
                t.c.actor_user_id == actor,
                t.c.payload["previous_status"].as_string() == "PENDING",
                t.c.payload["new_status"].as_string() == "ACCEPTED",
            )
            .order_by(t.c.created_at, t.c.id)
            .limit(1)
        )
    row = (
        session.execute(
            query.where(
                t.c.organization_id == ops.ORGANIZATION_ID,
                t.c.branch_id == branch,
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def order_acceptance(
    session: Session,
    actor: str,
    order: str,
    execute: Callable[[bool], dict[str, Any]],
    *,
    driver: str | None = None,
    assignment: bool = False,
    commit: bool,
) -> dict[str, Any]:
    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        branch = _branch(session, models.orders, order)
        revision = require_receipt_access(session, actor, branch)
        if revision is None:
            result = execute(commit)
            if commit and require_receipt_access(session, actor, branch) is not None:
                raise ops.BusinessError("cash_authorization_changed", "Policy changed")
            return result
        fact = _order_fact(session, actor, branch, order, assignment)
        if fact is None:
            ops._require_order_write_fence(session, branch)
            fact = _order_fact(session, actor, branch, order, assignment)
        if fact is None:
            if not assignment:
                status = session.scalar(
                    sa.select(models.orders.c.status).where(
                        models.orders.c.id == order,
                        models.orders.c.organization_id == ops.ORGANIZATION_ID,
                    )
                )
                if status != "PENDING":
                    deny()
            execute(False)
            fact = _order_fact(session, actor, branch, order, assignment)
        if fact is None:
            raise ops.BusinessError("command_result_unavailable", "Acceptance is unavailable")
        if fact["actor_user_id"] != actor:
            deny()
        if assignment and fact["driver_id"] != str(driver or "").strip():
            raise ops.BusinessError("delivery_assignment_conflict", "Assignment intention changed")
        return _finish(
            session,
            actor,
            branch,
            revision,
            order,
            "delivery_assignment" if assignment else "pending_order",
            fact,
            commit=commit,
        )
    except Exception:
        if commit:
            session.rollback()
        raise

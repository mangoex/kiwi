"""Own correction acknowledgements, isolated from immutable financial snapshots."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import deny, governance_lock
from restaurant_os.order_command_receipts import command_metadata, require_receipt_access

Action = Literal["request", "approve", "reject", "apply"]


class OrderReopenReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    action: Literal[
        "order.reopen.request", "order.reopen.approve", "order.reopen.reject", "order.reopen.apply"
    ]
    command_id: str
    id: str
    request_id: str
    order_id: str
    branch_id: str
    status: Literal["REQUESTED", "APPROVED", "REJECTED", "APPLIED"]
    accepted_at: datetime
    correction_id: str | None = None


def reopen_digest(action: Action, target: str, payload: dict[str, Any], actor: str) -> str:
    if action == "apply":
        return ops._pco005_hash({"request_id": target, "actor_user_id": actor, "payload": payload})
    if action == "request":
        evidence = payload.get("evidence_refs", [])
        return ops._pco005_hash(
            {
                "order_id": target,
                "reason": str(payload.get("reason") or "").strip(),
                "evidence_refs": [str(value).strip() for value in evidence]
                if isinstance(evidence, list)
                else [],
            }
        )
    return ops._pco005_hash(
        {
            "request_id": target,
            "decision": "APPROVED" if action == "approve" else "REJECTED",
            "decision_reason": str(payload.get("decision_reason") or "").strip(),
        }
    )


def _metadata(session: Session, target: str, *, order: bool = False) -> dict[str, Any]:
    table = models.orders if order else models.order_reopen_requests
    row = (
        session.execute(
            sa.select(table.c.id, table.c.branch_id, *([] if order else [table.c.order_id])).where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.id == target,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ops.NotFoundError(
            "order_not_found" if order else "order_reopen_request_not_found",
            "Resource was not found",
        )
    return dict(row)


def _stored(session: Session, key: str) -> dict[str, Any] | None:
    table = models.order_reopen_commands
    row = (
        session.execute(
            command_metadata(table).where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def reopen_command(
    session: Session,
    actor: str,
    action: Action,
    target: str,
    payload: dict[str, Any],
    key: str | None,
    execute: Callable[[bool], dict[str, Any]],
) -> dict[str, Any]:
    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        normalized_key = ops._pco005_key(key)
        ops._acquire_idempotency_lock(session, "order-reopen-receipt", normalized_key)
        stored = _stored(session, normalized_key)
        scope = _metadata(
            session,
            str(stored["request_id"]) if stored else target,
            order=stored is None and action == "request",
        )
        branch = str(scope["branch_id"])
        revision = require_receipt_access(session, actor, branch)
        if revision is None:
            result = execute(True)
            if require_receipt_access(session, actor, branch) is not None:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Policy changed during receipt delivery"
                )
            return result
        digest = reopen_digest(action, target, payload, actor)
        if stored is not None:
            if stored["actor_user_id"] != actor:
                deny()
            stored_target = stored["order_id"] if action == "request" else stored["request_id"]
            if (
                stored["command_type"] != action
                or stored["request_hash"] != digest
                or stored_target != target
            ):
                raise ops.BusinessError("idempotency_conflict", "Command identity changed")
        else:
            # Enter the branch fence before the core locks request/order rows. The
            # core keeps its existing functional/Owner guards and compensation rules.
            ops._require_order_write_fence(session, branch)
            execute(False)
            stored = _stored(session, normalized_key)
        if (
            stored is None
            or stored["status"] != "completed"
            or stored["actor_user_id"] != actor
            or stored["command_type"] != action
            or stored["request_hash"] != digest
        ):
            raise ops.BusinessError("command_result_unavailable", "Command result is unavailable")
        persisted_scope = _metadata(session, str(stored["request_id"]))
        if (
            persisted_scope["branch_id"] != branch
            or persisted_scope["order_id"] != stored["order_id"]
        ):
            deny()
        correction = None
        if action == "apply":
            table = models.order_corrections
            correction = session.scalar(
                sa.select(table.c.id).where(
                    table.c.organization_id == ops.ORGANIZATION_ID,
                    table.c.branch_id == branch,
                    table.c.request_id == stored["request_id"],
                    table.c.order_id == stored["order_id"],
                    table.c.status == "APPLIED",
                )
            )
            if correction is None:
                raise ops.BusinessError(
                    "command_result_unavailable", "Command result is unavailable"
                )
        result = OrderReopenReceiptV2.model_validate(
            {
                "policy_version": revision,
                "action": "order.reopen." + action,
                "command_id": stored["id"],
                "id": stored["request_id"],
                "request_id": stored["request_id"],
                "order_id": stored["order_id"],
                "branch_id": branch,
                "accepted_at": stored["created_at"],
                "correction_id": correction,
                "status": {
                    "request": "REQUESTED",
                    "approve": "APPROVED",
                    "reject": "REJECTED",
                    "apply": "APPLIED",
                }[action],
            }
        ).model_dump(mode="json")
        ops._audit(
            session,
            "order.reopen.receipt_read",
            "order_reopen_request",
            stored["request_id"],
            {"command_id": stored["id"], "action": action, "policy_version": revision},
            branch_id=branch,
            actor_user_id=actor,
        )
        session.commit()
        if require_receipt_access(session, actor, branch) != revision:
            raise ops.BusinessError(
                "cash_authorization_changed", "Policy changed during receipt delivery"
            )
        return result
    except Exception:
        session.rollback()
        raise

"""Amendment receipts are independent of historical order and delivery amounts."""

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
from restaurant_os.order_command_receipts import require_receipt_access


class OrderAmendmentReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    action: Literal["order.amend"] = "order.amend"
    command_id: str
    id: str
    order_id: str
    branch_id: str
    status: Literal["accepted"] = "accepted"
    version: int
    accepted_at: datetime


def amendment_digest(
    lines: list[dict[str, Any]], expected_version: int, selection: Any, reference: Any
) -> str:
    return ops._pco005_hash(
        {
            "lines": lines,
            "expected_version": expected_version,
            "delivery_selection": selection,
            "delivery_quote_reference": reference,
        }
    )


def _stored(session: Session, order: str, key: str) -> dict[str, Any] | None:
    table = models.order_amendments
    row = (
        session.execute(
            sa.select(
                table.c.id,
                table.c.order_id,
                table.c.actor_user_id,
                table.c.expected_version,
                table.c.resulting_version,
                table.c.created_at,
                sa.func.coalesce(
                    table.c.after_snapshot["command_hash"].as_string(),
                    table.c.after_snapshot["delivery_command_hash"].as_string(),
                ).label("request_hash"),
            ).where(table.c.order_id == order, table.c.idempotency_key == key)
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def amendment_command(
    session: Session,
    actor: str,
    order: str,
    key: str,
    digest: str | None,
    execute: Callable[[bool], dict[str, Any]] | None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        normalized_key = key.strip()
        if not normalized_key:
            raise ops.BusinessError("idempotency_key_required", "Idempotency-Key is required")
        ops._acquire_idempotency_lock(
            session, "order-amendment-receipt", order + ":" + normalized_key
        )
        branch = session.scalar(
            sa.select(models.orders.c.branch_id).where(
                models.orders.c.id == order,
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        if branch is None:
            raise ops.NotFoundError("order_not_found", "Order was not found")
        revision = require_receipt_access(session, actor, branch)
        if revision is None:
            if execute is None:
                raise ops.BusinessError(
                    "cash_projection_not_available", "Receipt policy is not active"
                )
            result = execute(commit)
            if commit and require_receipt_access(session, actor, branch) is not None:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Policy changed during receipt delivery"
                )
            return result
        stored = _stored(session, order, normalized_key)
        if stored is not None:
            if stored["actor_user_id"] != actor:
                deny()
            if execute is not None:
                if stored["request_hash"] is None:
                    raise ops.BusinessError(
                        "order_amendment_recovery_required",
                        "Recover the historical acknowledgement separately",
                    )
                if stored["request_hash"] != digest:
                    raise ops.BusinessError(
                        "idempotency_key_conflict", "Amendment intention changed"
                    )
        else:
            if execute is None:
                raise ops.NotFoundError("order_amendment_not_found", "Amendment was not found")
            ops._require_order_write_fence(session, branch)
            execute(False)
            stored = _stored(session, order, normalized_key)
            if stored is None or stored["request_hash"] != digest:
                raise ops.BusinessError(
                    "command_result_unavailable", "Command result is unavailable"
                )
        if stored["actor_user_id"] != actor:
            deny()
        result = OrderAmendmentReceiptV2(
            policy_version=revision,
            command_id=stored["id"],
            id=order,
            order_id=order,
            branch_id=branch,
            version=stored["resulting_version"],
            accepted_at=stored["created_at"],
        ).model_dump(mode="json")
        ops._audit(
            session,
            "order.amendment.receipt_read",
            "order_amendment",
            stored["id"],
            {"order_id": order, "policy_version": revision},
            branch_id=branch,
            actor_user_id=actor,
        )
        if commit:
            session.commit()
            if require_receipt_access(session, actor, branch) != revision:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Policy changed during receipt delivery"
                )
        return result
    except Exception:
        if commit:
            session.rollback()
        raise


def recover_amendment(session: Session, order: str, key: str, actor: str) -> dict[str, Any]:
    return amendment_command(session, actor, order, key, None, None)

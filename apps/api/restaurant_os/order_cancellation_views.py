"""Cancellation result projection without the historical order's private fields."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import governance_lock
from restaurant_os.order_command_receipts import require_receipt_access


class OrderCancellationReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    action: Literal["order.cancel"] = "order.cancel"
    id: str
    order_id: str
    branch_id: str
    status: Literal["CANCELLED"] = "CANCELLED"
    cancellation_kind: Literal["reservation_release", "waste", "recovery"]
    classification: str | None


def cancellation_command(
    session: Session,
    actor: str,
    order: str,
    execute: Callable[[bool], dict[str, Any]],
    *,
    commit: bool,
    authorize: Callable[[], None] | None = None,
) -> dict[str, Any]:
    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        branch = session.scalar(
            sa.select(models.orders.c.branch_id).where(
                models.orders.c.id == order,
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        if branch is None:
            raise ops.BusinessError("order_not_found", "Order was not found")
        revision = require_receipt_access(session, actor, branch)
        if revision is None:
            result = execute(commit)
            if commit and require_receipt_access(session, actor, branch) is not None:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Policy changed during receipt delivery"
                )
            return result
        # Serialize before the core reads status, not after it has cached an eligible order.
        ops._require_order_write_fence(session, branch)
        if authorize is not None:
            authorize()
        changed = execute(False)
        result = OrderCancellationReceiptV2(
            policy_version=revision,
            id=order,
            order_id=order,
            branch_id=branch,
            cancellation_kind=changed["cancellation_kind"],
            classification=changed["classification"],
        ).model_dump(mode="json")
        ops._audit(
            session,
            "order.cancellation.receipt_read",
            "order",
            order,
            {"policy_version": revision},
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

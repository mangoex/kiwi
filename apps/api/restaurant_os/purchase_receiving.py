"""Branch-scoped quantities for receiving; prices remain a separate authority."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import (
    FinancialAuthority,
    governance_lock,
    protected_policy_revision,
)


class ReceivingLine(FinancialRecord):
    allocation_id: str
    warehouse_id: str
    item_id: str
    item_name: str
    presentation_id: str
    presentation_name: str
    presentation_quantity: Decimal
    received_quantity: Decimal
    pending_quantity: Decimal


class ReceivingOrder(FinancialRecord):
    id: str
    folio: str
    status: str
    version: int
    lines: list[ReceivingLine]


class ReceivingPage(FinancialRecord):
    projection: Literal["operational"] = "operational"
    schema_version: Literal[2] = 2
    policy_version: int
    branch_id: str
    items: list[ReceivingOrder]
    next_cursor: str | None


class ReceiptLine(FinancialRecord):
    id: str
    allocation_id: str
    presentation_quantity: Decimal
    base_quantity: Decimal


class Receipt(FinancialRecord):
    id: str
    order_id: str
    branch_id: str
    warehouse_id: str
    received_at: datetime
    received_by: str
    discrepancy_reason: str | None
    lines: list[ReceiptLine]


class ReceivingReceipt(FinancialRecord):
    projection: Literal["operational"] = "operational"
    schema_version: Literal[2] = 2
    policy_version: int
    receipt: Receipt


def authority(session: Session, actor: str, branch: str, *, required: bool = False) -> int | None:
    governance_lock(session, ops.ORGANIZATION_ID)
    revision = protected_policy_revision(session, ops.ORGANIZATION_ID, branch)
    if revision is None:
        if required:
            raise ops.BusinessError(
                "cash_projection_not_available", "Receiving policy is not active"
            )
        return None
    FinancialAuthority(session, actor, ops.ORGANIZATION_ID).require_capability(
        "purchases.receive", branch
    )
    return revision


def receipt_projection(
    session: Session, receipt_id: str, branch: str, revision: int
) -> dict[str, Any]:
    receipts, lines = models.corporate_purchase_receipts, models.corporate_purchase_receipt_lines
    row = (
        session.execute(
            sa.select(
                receipts.c.id,
                receipts.c.order_id,
                receipts.c.branch_id,
                receipts.c.warehouse_id,
                receipts.c.received_at,
                receipts.c.received_by,
            ).where(
                receipts.c.id == receipt_id,
                receipts.c.branch_id == branch,
                receipts.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ops.AuthorizationError("financial_access_denied", "Receipt access denied")
    reason = session.scalar(
        sa.select(models.audit_events.c.payload["discrepancy_reason"].as_string()).where(
            models.audit_events.c.organization_id == ops.ORGANIZATION_ID,
            models.audit_events.c.branch_id == branch,
            models.audit_events.c.action == "corporate_purchase.received",
            models.audit_events.c.payload["receipt_id"].as_string() == receipt_id,
        )
    )
    items = (
        session.execute(
            sa.select(
                lines.c.id,
                lines.c.allocation_id,
                lines.c.presentation_quantity,
                lines.c.base_quantity,
            )
            .where(lines.c.receipt_id == receipt_id)
            .order_by(lines.c.id)
        )
        .mappings()
        .all()
    )
    return ReceivingReceipt(
        policy_version=revision,
        receipt=Receipt.model_validate({**row, "lines": list(items), "discrepancy_reason": reason}),
    ).model_dump(mode="json")


def receiving_page(
    session: Session, actor: str, branch: str, cursor: str | None, limit: int
) -> dict[str, Any]:
    revision = authority(session, actor, branch, required=True)
    assert revision is not None
    if not 1 <= limit <= 50:
        raise ops.BusinessError("receiving_limit_invalid", "Use limit 1..50")
    orders, lines, allocations = (
        models.corporate_purchase_orders,
        models.corporate_purchase_order_lines,
        models.corporate_purchase_allocations,
    )
    assigned = sa.exists(
        sa.select(allocations.c.id)
        .select_from(allocations.join(lines))
        .where(lines.c.order_id == orders.c.id, allocations.c.branch_id == branch)
    )
    query = sa.select(orders.c.id, orders.c.folio, orders.c.status, orders.c.version).where(
        orders.c.organization_id == ops.ORGANIZATION_ID,
        orders.c.status.in_(("APPROVED", "PARTIALLY_RECEIVED")),
        assigned,
    )
    if cursor:
        query = query.where(orders.c.id > cursor)
    rows = session.execute(query.order_by(orders.c.id).limit(limit + 1)).mappings().all()
    result = []
    for row in rows[:limit]:
        items = (
            session.execute(
                sa.select(
                    allocations.c.id.label("allocation_id"),
                    allocations.c.warehouse_id,
                    lines.c.item_id,
                    models.inventory_items.c.name.label("item_name"),
                    lines.c.presentation_id,
                    lines.c.presentation_snapshot["name"].as_string().label("presentation_name"),
                    allocations.c.presentation_quantity,
                    allocations.c.received_presentation_quantity.label("received_quantity"),
                    (
                        allocations.c.presentation_quantity
                        - allocations.c.received_presentation_quantity
                    ).label("pending_quantity"),
                )
                .select_from(
                    allocations.join(lines).join(
                        models.inventory_items, lines.c.item_id == models.inventory_items.c.id
                    )
                )
                .where(lines.c.order_id == row["id"], allocations.c.branch_id == branch)
                .order_by(allocations.c.id)
            )
            .mappings()
            .all()
        )
        result.append(ReceivingOrder.model_validate({**row, "lines": list(items)}))
    return ReceivingPage(
        policy_version=revision,
        branch_id=branch,
        items=result,
        next_cursor=str(rows[limit - 1]["id"]) if len(rows) > limit else None,
    ).model_dump(mode="json")

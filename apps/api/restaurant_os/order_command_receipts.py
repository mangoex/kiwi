"""Closed own-command acknowledgements; historical monetary snapshots remain internal."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock


class OrderCommandReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    action: Literal["order.create", "payment.confirm"]
    command_id: str
    id: str
    order_id: str
    branch_id: str
    status: Literal["accepted"] = "accepted"
    accepted_at: datetime


def command_metadata(table: sa.Table) -> sa.Select[Any]:
    return sa.select(*(column for column in table.c if column.name != "response_snapshot"))


def require_receipt_access(session: Session, actor: str, branch: str) -> int | None:
    governance_lock(session, ops.ORGANIZATION_ID)
    if active_revision(session, branch) is None:
        return None
    revision = FinancialAuthority(session, actor, ops.ORGANIZATION_ID).policy_revision(branch)
    if not ops._actor_has_permission(session, actor, "orders.read", branch):
        deny()
    return revision


def legacy_snapshot(session: Session, table: sa.Table, command: dict[str, Any]) -> dict[str, Any]:
    value = session.scalar(
        sa.select(table.c.response_snapshot).where(
            table.c.id == command["id"],
            table.c.organization_id == ops.ORGANIZATION_ID,
            table.c.actor_user_id == command["actor_user_id"],
        )
    )
    if not isinstance(value, dict):
        raise ops.BusinessError("command_result_unavailable", "Command result is unavailable")
    return value


def command_receipt(
    session: Session,
    command: dict[str, Any],
    actor: str,
    action: Literal["order.create", "payment.confirm"],
    *,
    commit: bool,
) -> dict[str, Any]:
    branch = str(command["branch_id"])
    revision = require_receipt_access(session, actor, branch)
    if (
        revision is None
        or command["actor_user_id"] != actor
        or command["organization_id"] != ops.ORGANIZATION_ID
    ):
        deny()
    assert revision is not None
    value = OrderCommandReceiptV2(
        policy_version=revision,
        action=action,
        command_id=command["id"],
        id=command["payment_id"] if action == "payment.confirm" else command["order_id"],
        order_id=command["order_id"],
        branch_id=branch,
        accepted_at=command["created_at"],
    ).model_dump(mode="json")
    ops._audit(
        session,
        "operational_command.receipt_read",
        "operational_command",
        command["id"],
        {"action": action, "order_id": command["order_id"], "policy_version": revision},
        branch_id=branch,
        actor_user_id=actor,
    )
    if commit:
        session.commit()
        if require_receipt_access(session, actor, branch) != revision:
            raise ops.BusinessError(
                "cash_authorization_changed", "Policy changed during receipt delivery"
            )
    return value


def payment_result(
    session: Session, command: dict[str, Any], actor: str, *, commit: bool
) -> dict[str, Any]:
    from restaurant_os import models

    if require_receipt_access(session, actor, str(command["branch_id"])) is not None:
        return command_receipt(session, command, actor, "payment.confirm", commit=commit)
    ops.require_permission(session, actor, "payments.confirm", command["branch_id"])
    return legacy_snapshot(session, models.payment_commands, command)

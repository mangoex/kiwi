"""Operational driver collection views; monetary history is never a replay DTO."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import Field
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import deny
from restaurant_os.order_command_receipts import legacy_snapshot, require_receipt_access


class DriverSettlementCandidateV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    id: str
    name: str
    status: str
    eligible_order_count: int = Field(ge=0)


class DriverSettlementReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    action: Literal["driver.cash_settlement.confirm"] = "driver.cash_settlement.confirm"
    command_id: str
    id: str
    branch_id: str
    driver_id: str
    status: Literal["CONFIRMED"]
    order_count: int = Field(ge=1, le=100)
    confirmed_at: datetime


def settlement_result(
    session: Session,
    command: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    branch = str(command["branch_id"])
    revision = require_receipt_access(session, actor, branch)
    if command["actor_user_id"] != actor or command["organization_id"] != ops.ORGANIZATION_ID:
        deny()
    if revision is None:
        ops.require_permission(session, actor, "payments.confirm", branch)
        value = legacy_snapshot(session, models.driver_cash_settlement_commands, command)
    else:
        table = models.driver_cash_settlements
        row = (
            session.execute(
                sa.select(
                    table.c.id,
                    table.c.branch_id,
                    table.c.driver_id,
                    table.c.status,
                    table.c.order_count,
                    table.c.confirmed_at,
                ).where(
                    table.c.id == command["settlement_id"],
                    table.c.organization_id == ops.ORGANIZATION_ID,
                    table.c.branch_id == branch,
                    table.c.actor_user_id == actor,
                    table.c.driver_id == command["driver_id"],
                    table.c.status == "CONFIRMED",
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ops.BusinessError("command_result_unavailable", "Command result is unavailable")
        value = DriverSettlementReceiptV2(
            **dict(row),
            policy_version=revision,
            command_id=command["id"],
        ).model_dump(mode="json")
        ops._audit(
            session,
            "driver.cash_settlement.receipt_read",
            "driver_cash_settlement",
            command["settlement_id"],
            {"command_id": command["id"], "policy_version": revision},
            branch_id=branch,
            actor_user_id=actor,
        )
    session.commit()
    if require_receipt_access(session, actor, branch) != revision:
        raise ops.BusinessError(
            "cash_authorization_changed", "Policy changed during receipt delivery"
        )
    return value

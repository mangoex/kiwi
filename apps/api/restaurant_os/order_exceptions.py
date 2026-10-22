"""One-use approvals bound to a human, branch, order, version and exact action."""

from __future__ import annotations

import json
from datetime import UTC, timedelta
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import (
    FinancialAuthority,
    governance_lock,
    protected_policy_revision,
)
from restaurant_os.order_exception_schema import CAPABILITY


class ExceptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["amend", "cancel"]
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    command: dict[str, Any]
    supervisor_identity: str = Field(min_length=1, max_length=180)
    supervisor_secret: str = Field(min_length=1, max_length=1024, repr=False)


class ExceptionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    projection: Literal["operational"] = "operational"
    schema_version: Literal[2] = 2
    policy_version: int
    authorization_id: str
    order_id: str
    action: Literal["amend", "cancel"]
    applied: bool


def receipt(session: Session, actor: str, order_id: str, identifier: str) -> dict[str, Any]:
    from restaurant_os.order_command_receipts import require_receipt_access

    governance_lock(session, ops.ORGANIZATION_ID)
    table = models.order_exception_authorizations
    row = (
        session.execute(
            sa.select(table.c.branch_id, table.c.action).where(
                table.c.id == identifier,
                table.c.order_id == order_id,
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.actor_user_id == actor,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ops.AuthorizationError("order_exception_denied", "Authorization receipt unavailable")
    revision = require_receipt_access(session, actor, str(row["branch_id"]))
    if revision is None:
        raise ops.AuthorizationError("order_exception_denied", "Protected policy is required")
    applied = (
        session.scalar(
            sa.select(models.order_exception_consumptions.c.authorization_id).where(
                models.order_exception_consumptions.c.authorization_id == identifier
            )
        )
        is not None
    )
    return ExceptionReceipt(
        policy_version=revision,
        authorization_id=identifier,
        order_id=order_id,
        action=row["action"],
        applied=applied,
    ).model_dump(mode="json")


def digest(action: str, version: int, reason: str, command: dict[str, Any]) -> str:
    if action == "amend":
        from restaurant_os.order_amendment_views import amendment_digest

        if set(command) - {
            "lines",
            "delivery_selection",
            "delivery_quote_reference",
        } or not isinstance(command.get("lines"), list):
            raise ops.BusinessError("order_exception_invalid", "Invalid amendment content")
        return amendment_digest(
            command["lines"],
            version,
            command.get("delivery_selection"),
            command.get("delivery_quote_reference"),
            reason,
        )
    if action != "cancel" or set(command) - {"classification"}:
        raise ops.BusinessError("order_exception_invalid", "Invalid cancellation content")
    return ops._pco005_hash(
        {
            "expected_version": version,
            "reason": reason,
            "classification": command.get("classification"),
        }
    )


def issue(session: Session, actor: str, order_id: str, request: ExceptionRequest) -> dict[str, Any]:
    governance_lock(session, ops.ORGANIZATION_ID)
    order = (
        session.execute(
            sa.select(models.orders.c.branch_id, models.orders.c.version)
            .where(
                models.orders.c.id == order_id,
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not order:
        raise ops.NotFoundError("order_not_found", "Order was not found")
    branch = str(order["branch_id"])
    revision = protected_policy_revision(session, ops.ORGANIZATION_ID, branch)
    if revision is None:
        raise ops.BusinessError("order_exception_policy_required", "Protected policy is required")
    ops.require_permission(session, actor, "orders." + request.action, branch)
    ops.require_permission(session, actor, "orders.read", branch)
    if order["version"] != request.expected_version:
        raise ops.BusinessError("order_version_conflict", "Order version changed")
    if not request.reason.strip() or len(json.dumps(request.command)) > 200_000:
        raise ops.BusinessError("order_exception_invalid", "Invalid reason or content")
    command_hash = digest(request.action, request.expected_version, request.reason, request.command)
    supervisor = ops.authorize_supervisor_step_up(
        session, request.supervisor_secret, branch, CAPABILITY, request.supervisor_identity
    )
    supervisor_id = str(supervisor["supervisor_user_id"])
    version = FinancialAuthority(session, supervisor_id, ops.ORGANIZATION_ID).require_capability(
        CAPABILITY, branch
    )
    now, identifier = ops._now(), ops._id()
    session.execute(
        models.order_exception_authorizations.insert().values(
            id=identifier,
            organization_id=ops.ORGANIZATION_ID,
            branch_id=branch,
            order_id=order_id,
            actor_user_id=actor,
            supervisor_user_id=supervisor_id,
            supervisor_version=version,
            action=request.action,
            expected_version=request.expected_version,
            request_hash=command_hash,
            reason=request.reason,
            authorized_at=now,
            expires_at=now + timedelta(minutes=2),
        )
    )
    ops._audit(
        session,
        "order.exception.authorized",
        "order_exception_authorization",
        identifier,
        {
            "order_id": order_id,
            "action": request.action,
            "expected_version": request.expected_version,
            "request_hash": command_hash,
            "reason": request.reason,
            "operator_id": actor,
        },
        branch_id=branch,
        actor_user_id=supervisor_id,
    )
    session.commit()
    return {
        "authorization_id": identifier,
        "expires_at": (now + timedelta(minutes=2)).isoformat(),
        "order_id": order_id,
        "action": request.action,
        "expected_version": request.expected_version,
    }


def consume(
    session: Session,
    actor: str,
    order_id: str,
    action: str,
    version: int | None,
    command_hash: str,
    authorization_id: str | None,
) -> None:
    governance_lock(session, ops.ORGANIZATION_ID)
    order = (
        session.execute(
            sa.select(models.orders.c.branch_id, models.orders.c.version)
            .where(
                models.orders.c.id == order_id,
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not order:
        raise ops.NotFoundError("order_not_found", "Order was not found")
    if protected_policy_revision(session, ops.ORGANIZATION_ID, str(order["branch_id"])) is None:
        return
    ops.require_permission(session, actor, "orders." + action, str(order["branch_id"]))
    row = (
        session.execute(
            sa.select(models.order_exception_authorizations)
            .where(
                models.order_exception_authorizations.c.id == authorization_id,
                models.order_exception_authorizations.c.organization_id == ops.ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not row or (
        row["actor_user_id"],
        row["order_id"],
        row["branch_id"],
        row["action"],
        row["expected_version"],
        row["request_hash"],
    ) != (actor, order_id, order["branch_id"], action, version, command_hash):
        raise ops.AuthorizationError(
            "order_exception_required", "Exact supervisor authorization is required"
        )
    if order["version"] != version:
        raise ops.BusinessError("order_version_conflict", "Order version changed")
    expires = row["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= ops._now():
        raise ops.AuthorizationError("order_exception_expired", "Authorization expired")
    if session.scalar(
        sa.select(models.order_exception_consumptions.c.authorization_id).where(
            models.order_exception_consumptions.c.authorization_id == authorization_id
        )
    ):
        raise ops.BusinessError("order_exception_consumed", "Authorization already consumed")
    FinancialAuthority(
        session, str(row["supervisor_user_id"]), ops.ORGANIZATION_ID
    ).require_capability(
        CAPABILITY, str(order["branch_id"]), expected_version=int(row["supervisor_version"])
    )
    session.execute(
        models.order_exception_consumptions.insert().values(
            authorization_id=authorization_id, consumed_at=ops._now()
        )
    )
    ops._audit(
        session,
        "order.exception.consumed",
        "order_exception_authorization",
        str(authorization_id),
        {
            "order_id": order_id,
            "action": action,
            "expected_version": version,
            "request_hash": command_hash,
            "supervisor_user_id": row["supervisor_user_id"],
            "reason": row["reason"],
        },
        branch_id=str(order["branch_id"]),
        actor_user_id=actor,
    )

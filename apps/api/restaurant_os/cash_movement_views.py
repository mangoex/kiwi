"""Human movement acknowledgements; the ledger and its snapshots remain internal."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import CashCommandReceiptV2, active_revision
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock


class CashMovementReceiptV2(CashCommandReceiptV2):
    action: Literal["cash.movement.create", "cash.movement.compensate"]
    status: Literal["confirmed"] = "confirmed"
    version: Literal[1] = 1


def _stored(session: Session, key: str) -> RowMapping | None:
    commands = models.cash_movement_commands
    return (
        session.execute(
            sa.select(
                commands.c.id,
                commands.c.actor_user_id,
                commands.c.target_movement_id,
                commands.c.command_type,
                commands.c.status,
                commands.c.request_hash,
                commands.c.created_at,
                commands.c.result["movement"]["id"].as_string().label("movement_id"),
            ).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )


def _metadata(session: Session, identifier: object) -> RowMapping:
    movement = models.cash_movements
    row = (
        session.execute(
            sa.select(
                movement.c.id,
                movement.c.branch_id,
                movement.c.cash_shift_id,
                movement.c.status,
                movement.c.actor_user_id,
                movement.c.compensates_movement_id,
                movement.c.reversal_of_id,
            ).where(
                movement.c.organization_id == ops.ORGANIZATION_ID,
                movement.c.id == identifier if isinstance(identifier, str) else sa.false(),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ops.BusinessError("cash_movement_not_found", "Cash movement was not found")
    return row


def _read(session: Session, actor: str, branch: str) -> int | None:
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    if active_revision(session, branch) is None:
        return None
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    revision = authority.policy_revision(branch)
    authority.require_capability("cash.shift.read", branch)
    return revision


def movement_command(
    session: Session,
    actor: str,
    action: Literal["create", "compensate"],
    target: str | None,
    payload: dict[str, Any],
    key: str,
    execute: Callable[[bool], dict[str, Any]],
    *,
    commit: bool,
) -> dict[str, Any]:
    """Wrap the canonical command, preserving the caller's outer transaction."""
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    key = ops._cash_movement_command_key(key)
    digest = ops._cash_movement_request_hash(
        action, actor, payload if action == "create" else {"movement_id": target, **payload}
    )
    stored = _stored(session, key)
    # A known key is scoped by server evidence, never by an altered request branch.
    if stored is not None:
        branch = str(_metadata(session, stored["target_movement_id"])["branch_id"])
    elif action == "compensate":
        branch = str(_metadata(session, target)["branch_id"])
    else:
        branch = str(payload.get("branch_id", "")).strip()
    revision = _read(session, actor, branch)
    if revision is None:
        result = execute(commit)
        if commit and _read(session, actor, branch) is not None:
            raise ops.BusinessError("cash_authorization_changed", "Policy changed during delivery")
        return result
    try:
        replay = stored is not None
        if stored is not None:
            if stored["actor_user_id"] != actor:
                deny()
            if stored["request_hash"] != digest or stored["command_type"] != action:
                raise ops.BusinessError("idempotency_conflict", "Command identity changed")
        else:
            # Canonical guards and immutable ledger/snapshots are unchanged.
            execute(False)
            stored = _stored(session, key)
        if stored is None or stored["actor_user_id"] != actor or stored["request_hash"] != digest:
            deny()
        assert stored is not None
        movement = _metadata(session, stored["movement_id"])
        if (
            movement["branch_id"] != branch
            or movement["actor_user_id"] != actor
            or stored["status"] != "completed"
            or movement["status"] != "confirmed"
            or (action == "create" and movement["id"] != stored["target_movement_id"])
            or (
                action == "compensate"
                and (
                    movement["compensates_movement_id"] != stored["target_movement_id"]
                    or movement["reversal_of_id"] != stored["target_movement_id"]
                )
            )
        ):
            raise ops.BusinessError(
                "cash_command_evidence_conflict", "Command evidence requires review"
            )
        value = CashMovementReceiptV2(
            command_id=stored["id"],
            resource_id=movement["id"],
            action="cash.movement.create" if action == "create" else "cash.movement.compensate",
            accepted_at=stored["created_at"],
            replay=replay,
            correlation_id=stored["id"],
            policy_version=revision,
        ).model_dump(mode="json")
        ops._audit(
            session,
            "cash_movement.receipt_read",
            "cash_movement",
            str(movement["id"]),
            {"command_id": stored["id"], "action": action, "policy_version": revision},
            branch_id=branch,
            actor_user_id=actor,
        )
        if commit:
            session.commit()
        if _read(session, actor, branch) != revision:
            raise ops.BusinessError("cash_authorization_changed", "Policy changed during delivery")
        return value
    except Exception:
        if commit:
            session.rollback()
        raise

"""Project cash command receipts without changing the immutable stored result."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import CashCommandReceiptV2, CashViews, active_revision
from restaurant_os.financial_authority import deny, governance_lock


def cut_command(
    service: ops.UserCashCutService,
    command: Callable[..., Any],
    action: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    session = service.session
    bound = inspect.signature(command).bind(service, *args, **kwargs).arguments
    actor = str(bound["actor_user_id"])
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    if not session.scalar(
        sa.select(models.blind_cash_policy_revisions.c.branch_id)
        .where(
            models.blind_cash_policy_revisions.c.organization_id == ops.ORGANIZATION_ID,
            models.blind_cash_policy_revisions.c.event == "activated",
        )
        .limit(1)
    ):
        return _execute(service, command, args, kwargs)
    # Identify scope with nonfinancial columns, before the canonical command reads its ledger.
    views = CashViews(session, actor)
    target = bound.get("cut_id") or bound.get("request_id")
    cut_id = bound.get("cut_id")
    if "request_id" in bound:
        cut_id = session.scalar(
            sa.select(models.user_cash_cut_reopen_requests.c.cash_cut_id).where(
                models.user_cash_cut_reopen_requests.c.organization_id == ops.ORGANIZATION_ID,
                models.user_cash_cut_reopen_requests.c.id == bound["request_id"],
            )
        )
    if action == "create":
        shift_id = bound.get("payload", {}).get("cash_shift_id")
        meta = views.metadata("shift", str(shift_id))
    else:
        meta = views.metadata("cut", str(cut_id))
    branch = str(meta["branch_id"])
    revision = active_revision(session, branch)
    if revision is None:
        return _execute(service, command, args, kwargs)
    key = service._key(str(bound["idempotency_key"]))
    payload = bound.get("payload", {})
    digest = service._hash(action, actor, target, payload)
    commands = models.user_cash_cut_commands
    stored = (
        session.execute(
            sa.select(
                commands.c.id,
                commands.c.actor_user_id,
                commands.c.cash_cut_id,
                commands.c.request_hash,
                commands.c.command_type,
                commands.c.created_at,
            ).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if stored is not None:
        if stored["actor_user_id"] != actor:
            deny()
        views.require_cut_read(views.metadata("cut", stored["cash_cut_id"]))
        if stored["request_hash"] != digest:
            raise ops.BusinessError("idempotency_conflict", "Command identity changed")
        service._pco006_replayed = True
    else:
        capability = {
            "create": "cash.user_cut.capture",
            "count": "cash.user_cut.capture",
            "finalize": "cash.user_cut.finalize",
            "reopen_request": "cash.user_cut.reopen.request",
        }.get(action, "cash.user_cut.reopen.authorize")
        views.authority.require_capability(capability, branch)
        if action == "create":
            views.authority.require_capability("cash.user_cut.operational.read", branch)
        else:
            views.require_cut_read(meta)
        # Phase 2 will supply substitution identity/reason. Do not infer them here.
        if action in {"create", "count"} and meta["cashier_user_id"] != actor:
            raise ops.BusinessError("cash_capture_not_ready", "Substitution capture is not ready")
        _execute(service, command, args, kwargs)
    # Canonical commands may commit, or roll back after an IntegrityError. Reacquire
    # current read authority in either case. Never serialize their raw return value.
    governance_lock(session, ops.ORGANIZATION_ID)
    require_same_policy(session, branch, revision)
    stored = (
        session.execute(
            sa.select(
                commands.c.id,
                commands.c.actor_user_id,
                commands.c.cash_cut_id,
                commands.c.request_hash,
                commands.c.command_type,
                commands.c.created_at,
            ).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .one()
    )
    if stored["actor_user_id"] != actor or stored["request_hash"] != digest:
        deny()
    resource = views.metadata("cut", str(stored["cash_cut_id"]))
    views.require_cut_read(resource)
    saved = (
        session.execute(
            sa.select(
                commands.c.result["cash_cut"]["status"].as_string().label("status"),
                commands.c.result["cash_cut"]["version"].as_integer().label("version"),
                commands.c.result["reopen_request"]["id"].as_string().label("request_id"),
                commands.c.result["reopen_request"]["status"].as_string().label("request_status"),
                commands.c.result["compensation"]["id"].as_string().label("compensation_id"),
            ).where(
                commands.c.id == stored["id"], commands.c.organization_id == ops.ORGANIZATION_ID
            )
        )
        .mappings()
        .one()
    )
    resource_id = stored["cash_cut_id"]
    status, version = saved["status"], saved["version"]
    if saved["request_id"] is not None or saved["compensation_id"] is not None:
        # A correction leaves the immutable finalized cut version unchanged.
        version = session.scalar(
            sa.select(models.user_cash_cuts.c.version).where(
                models.user_cash_cuts.c.id == stored["cash_cut_id"],
                models.user_cash_cuts.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        resource_id = saved["request_id"] or saved["compensation_id"]
        status = saved["request_status"] or "COMPENSATED"
    return CashCommandReceiptV2(
        command_id=stored["id"],
        resource_id=resource_id,
        action=stored["command_type"],
        status=status,
        version=version,
        accepted_at=stored["created_at"],
        replay=service._pco006_replayed,
        correlation_id=stored["id"],
        policy_version=revision,
    ).model_dump(mode="json")


def _execute(
    service: ops.UserCashCutService,
    command: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    try:
        result: dict[str, Any] = command(service, *args, **kwargs)
        return result
    except ops._UserCashCutCommandReplay as replay:
        service._pco006_replayed = True
        return replay.result


def shift_command(
    session: Session,
    actor: str,
    action: str,
    target: str | None,
    payload: dict[str, Any],
    key: str,
    *,
    intent: str | None,
    context: str | None,
) -> dict[str, Any]:
    from restaurant_os.api import _require_operational_workspace
    from restaurant_os.config import get_settings
    from restaurant_os.operational_intents import execute_intent

    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    views = CashViews(session, actor)
    branch = (
        str(payload["branch_id"])
        if action == "open"
        else str(views.metadata("shift", str(target))["branch_id"])
    )
    revision = views.revision(branch)
    key = ops.UserCashCutService._key(key)
    digest = ops._cash_shift_command_hash(action, actor, target, payload)
    commands = models.cash_shift_commands

    def persisted() -> Any:
        return (
            session.execute(
                sa.select(commands).where(
                    commands.c.organization_id == ops.ORGANIZATION_ID,
                    commands.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )

    stored = persisted()
    replay = stored is not None
    if stored is not None:
        if stored["actor_user_id"] != actor:
            deny()
        meta = views.metadata("shift", stored["cash_shift_id"])
        views.authority.require_capability("cash.shift.read", str(meta["branch_id"]))
        if stored["request_hash"] != digest:
            raise ops.BusinessError("idempotency_conflict", "Command identity changed")
    else:
        views.authority.require_capability(f"cash.shift.{action}", branch)
        _require_operational_workspace(session, actor, branch, context)

        def execute() -> dict[str, Any]:
            if action == "open":
                ops.open_cash_shift_idempotently(
                    session,
                    branch,
                    payload["register_id"],
                    payload["opening_cash_cents"],
                    key,
                    actor,
                    commit=False,
                )
            else:
                ops.close_cash_shift_operationally(session, str(target), key, actor, commit=False)
            # The intent envelope also receives only an operational receipt.
            return receipt()

        def receipt() -> dict[str, Any]:
            current = persisted()
            if current is None:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Command evidence unavailable"
                )
            views.authority.require_capability("cash.shift.read", branch)
            return CashCommandReceiptV2(
                command_id=current["id"],
                resource_id=current["cash_shift_id"],
                action=action,
                status="OPEN" if action == "open" else "OPERATIVELY_CLOSED",
                version=1 if action == "open" else 2,
                accepted_at=current["created_at"],
                replay=False,
                correlation_id=current["id"],
                policy_version=revision,
            ).model_dump(mode="json")

        try:
            if get_settings().branch_scope_v2_enabled:
                execute_intent(
                    session,
                    actor,
                    intent,
                    f"cash.shift.{action}",
                    target,
                    payload,
                    key,
                    context,
                    execute,
                )
            else:
                execute()
                session.commit()
        except Exception:
            session.rollback()
            raise
    # Covers the commit boundary of both direct commands and operational intents.
    governance_lock(session, ops.ORGANIZATION_ID)
    require_same_policy(session, branch, revision)
    views.authority.require_capability("cash.shift.read", branch)
    stored = persisted()
    if stored is None or stored["actor_user_id"] != actor or stored["request_hash"] != digest:
        deny()
    return CashCommandReceiptV2(
        command_id=stored["id"],
        resource_id=stored["cash_shift_id"],
        action=action,
        status="OPEN" if action == "open" else "OPERATIVELY_CLOSED",
        version=1 if action == "open" else 2,
        accepted_at=stored["created_at"],
        replay=replay,
        correlation_id=stored["id"],
        policy_version=revision,
    ).model_dump(mode="json")


def require_same_policy(session: Session, branch: str, revision: int) -> None:
    if active_revision(session, branch) != revision:
        raise ops.BusinessError("cash_authorization_changed", "Refresh current cash policy")

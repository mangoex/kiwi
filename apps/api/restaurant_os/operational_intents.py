"""Prepare before sending; confirm with the domain; resolve only from server evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.branch_workspaces import _lock_actor, _uuid, validate_branch_context
from restaurant_os.cash_views import active_revision
from restaurant_os.config import get_settings
from restaurant_os.financial_authority import FinancialAuthority
from restaurant_os.offline_authorization import authority_now, rollback_reconciliation
from restaurant_os.operational_intent_schema import (
    CASH_LIFECYCLE_KINDS,
    LEGACY_KINDS,
    command_namespace,
)
from restaurant_os.order_command_receipts import require_receipt_access
from restaurant_os.order_execution import defer_authorization_audit, without_order_execution_context

KINDS = (*LEGACY_KINDS, *CASH_LIFECYCLE_KINDS)
TARGETED_KINDS = ("payment.confirm", "cash.shift.close", "cash.movement.compensate")


def _require_registry(session: Session) -> None:
    inspector = sa.inspect(session.connection())
    if not inspector.has_table("operational_command_intents") or "command_namespace" not in {
        column["name"] for column in inspector.get_columns("operational_command_intents")
    }:
        raise ops.BusinessError(
            "operational_command_migration_required", "Command registry migration is required"
        )


@contextmanager
def _unit(session: Session) -> Iterator[None]:
    with without_order_execution_context():
        try:
            yield
        except SQLAlchemyError:
            rollback_reconciliation(session)
            raise ops.BusinessError(
                "operational_command_persistence_unavailable",
                "Command evidence is temporarily unavailable",
            ) from None
        except Exception:
            rollback_reconciliation(session)
            raise


def _lock(session: Session, actor: str) -> None:
    _require_registry(session)
    ops._authority_governance_lock(session)
    _lock_actor(session, actor)


def assert_transition_allowed(session: Session, actor: str) -> None:
    # This guard participates in the caller's already-held governance/actor fence.
    _require_registry(session)
    if session.scalar(
        sa.select(models.operational_command_intents.c.id)
        .where(
            models.operational_command_intents.c.organization_id == ops.ORGANIZATION_ID,
            models.operational_command_intents.c.actor_user_id == actor,
            models.operational_command_intents.c.state.in_(("prepared", "applied")),
        )
        .limit(1)
    ):
        raise ops.BusinessError(
            "branch_switch_uncertain_command", "Recover the pending command before changing branch"
        )


def _identity(kind: str, target: object, body: dict[str, Any], key: str | None) -> tuple[str, str]:
    if kind not in KINDS or (kind not in TARGETED_KINDS and target is not None):
        raise ops.BusinessError(
            "operational_command_payload_invalid", "Command identity is invalid"
        )
    if kind in TARGETED_KINDS:
        _uuid(target)
    if not isinstance(key, str):
        raise ops.BusinessError("idempotency_key_invalid", "A stable command key is required")
    key = key.strip()
    minimum, maximum = (1, 180) if kind.startswith("cash.") else (12, 160)
    if not minimum <= len(key) <= maximum:
        raise ops.BusinessError("idempotency_key_invalid", "A stable command key is required")
    try:
        digest = hashlib.sha256(
            json.dumps(
                {"kind": kind, "target_id": target, "payload": body},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
    except (ValueError, TypeError):
        raise ops.BusinessError(
            "operational_command_payload_invalid", "Command body is invalid"
        ) from None
    return key, digest


def _authority(
    session: Session,
    actor: str,
    kind: str,
    target: object,
    body: dict[str, Any],
    secret: str | None,
) -> dict[str, Any]:
    if not get_settings().branch_scope_v2_enabled:
        raise ops.BusinessError(
            "branch_scope_v2_disabled", "Command preparation requires workspace V2"
        )
    if kind == "payment.confirm":
        branch = session.scalar(
            sa.select(models.orders.c.branch_id).where(
                models.orders.c.organization_id == ops.ORGANIZATION_ID, models.orders.c.id == target
            )
        )
        permission = "payments.confirm"
    elif kind in ("cash.shift.close", "cash.movement.compensate"):
        source = models.cash_shifts if kind == "cash.shift.close" else models.cash_movements
        branch = session.scalar(
            sa.select(source.c.branch_id).where(
                source.c.organization_id == ops.ORGANIZATION_ID, source.c.id == target
            )
        )
        permission = (
            "cash.shift.close" if kind == "cash.shift.close" else "cash.movement.compensate"
        )
    else:
        branch = body.get("branch_id")
        permission = "orders.create"
        if kind in ("cash.shift.open", "cash.shift.close.register"):
            branch = str(body.get("branch_id", "")).strip()
            permission = "cash.shift.open" if kind == "cash.shift.open" else "cash.shift.close"
        if kind == "cash.movement.create":
            branch = str(body.get("branch_id", "")).strip()
            movement_type = str(body.get("movement_type", "")).strip().lower()
            if movement_type not in ("deposit", "withdrawal"):
                raise ops.BusinessError("cash_movement_invalid", "Movement type is invalid")
            permission = (
                "cash.movement.deposit" if movement_type == "deposit" else "cash.movement.withdraw"
            )
    if not isinstance(branch, str):
        raise ops.BusinessError("operational_command_payload_invalid", "Command branch is required")
    try:
        workspace = validate_branch_context(session, actor, branch, secret)
    except ops.AuthorizationError as error:
        audit_branch = session.scalar(
            sa.select(models.branches.c.id).where(
                models.branches.c.organization_id == ops.ORGANIZATION_ID,
                models.branches.c.id == branch,
            )
        )
        ops._record_authorization_denied(
            session,
            actor_user_id=actor,
            permission_code="branch.workspace",
            branch_id=audit_branch,
            reason=error.code,
        )
        raise
    ops.require_permission(session, actor, permission, branch)
    if kind == "cash.movement.compensate":
        ops._require_cash_compensation_owner(session, actor, branch)
    return workspace


def _receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {name: row[name] for name in ("id", "kind", "branch_id", "state", "resource_id")}


def _read_authority(session: Session, actor: str, kind: str, branch: str) -> int | None:
    # Caller holds governance/actor fences. Reading an own receipt is not execution.
    if kind in ("order.create", "payment.confirm"):
        return require_receipt_access(session, actor, branch)
    if active_revision(session, branch) is None:
        return None
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    revision = authority.policy_revision(branch)
    authority.require_capability("cash.shift.read", branch)
    return revision


def _revalidate_read(
    session: Session, actor: str, row: Mapping[str, Any], revision: int | None
) -> None:
    # The outer commit released locks; reacquire them even for a legacy-to-new transition.
    ops._authority_governance_lock(session)
    _lock_actor(session, actor)
    if _read_authority(session, actor, str(row["kind"]), str(row["branch_id"])) != revision:
        raise ops.BusinessError(
            "cash_authorization_changed", "Policy changed during receipt delivery"
        )


def _command(session: Session, row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    source = {
        "order.create": models.order_create_commands,
        "payment.confirm": models.payment_commands,
        "cash.movement.create": models.cash_movement_commands,
        "cash.movement.compensate": models.cash_movement_commands,
        "cash.shift.open": models.cash_shift_commands,
        "cash.shift.close": models.cash_shift_commands,
        "cash.shift.close.register": models.cash_shift_commands,
    }[row["kind"]]
    fields = [source.c.id, source.c.actor_user_id, source.c.request_hash]
    if row["kind"] in ("order.create", "payment.confirm"):
        fields.extend([source.c.branch_id, source.c.order_id])
        if row["kind"] == "payment.confirm":
            fields.append(source.c.payment_id)
    else:
        fields.extend([source.c.command_type, source.c.status])
        if row["kind"].startswith("cash.shift."):
            fields.extend(
                [
                    source.c.cash_shift_id,
                    source.c.result["cash_shift_id"].as_string().label("result_shift_id"),
                    source.c.result["closure_id"].as_string().label("result_closure_id"),
                ]
            )
        else:
            fields.extend(
                [
                    source.c.target_movement_id,
                    source.c.result["movement"]["id"].as_string().label("result_movement_id"),
                ]
            )
    command = (
        session.execute(
            sa.select(*fields).where(
                source.c.organization_id == row["organization_id"],
                source.c.idempotency_key == row["idempotency_key"],
            )
        )
        .mappings()
        .first()
    )
    return dict(command) if command else None


def _proof(session: Session, row: Mapping[str, Any]) -> dict[str, Any]:
    command = _command(session, row)
    valid = bool(command and command["actor_user_id"] == row["actor_user_id"])
    resource_id = None
    if command and valid:
        if row["kind"] == "cash.movement.create":
            resource_id = command["target_movement_id"]
            resource = models.cash_movements
            valid = command["command_type"] == "create" and command["status"] == "completed"
        elif row["kind"] == "cash.movement.compensate":
            resource_id = command["result_movement_id"]
            resource = models.cash_movements
            valid = (
                command["command_type"] == "compensate"
                and command["status"] == "completed"
                and command["target_movement_id"] == row["target_id"]
            )
        elif row["kind"].startswith("cash.shift."):
            if row["kind"] == "cash.shift.open":
                resource_id = command["cash_shift_id"]
                resource = models.cash_shifts
                valid = (
                    command["command_type"] == "open" and command["result_shift_id"] == resource_id
                )
            else:
                resource_id = command["result_closure_id"]
                resource = models.cash_shift_closures
                valid = command["command_type"] == "close" and (
                    row["target_id"] is None or command["cash_shift_id"] == row["target_id"]
                )
            valid = valid and command["status"] == "completed"
        elif row["kind"] == "payment.confirm":
            resource_id = command["payment_id"]
            resource = models.payments
            valid = command["order_id"] == row["target_id"]
        else:
            resource_id = command["order_id"]
            resource = models.orders
        try:
            _uuid(resource_id)
        except ops.BusinessError:
            raise ops.BusinessError(
                "operational_command_evidence_conflict", "Command resource evidence requires review"
            ) from None
        fields = [resource.c.id]
        if row["kind"] == "payment.confirm":
            fields.append(resource.c.order_id)
        elif row["kind"] == "cash.shift.open":
            fields.append(resource.c.cashier_user_id)
        elif row["kind"] in ("cash.shift.close", "cash.shift.close.register"):
            fields.extend([resource.c.cash_shift_id, resource.c.closed_by_user_id])
        binding = (
            session.execute(
                sa.select(*fields).where(
                    resource.c.id == resource_id,
                    resource.c.organization_id == row["organization_id"],
                    resource.c.branch_id == row["branch_id"],
                )
            )
            .mappings()
            .first()
        )
        valid = valid and binding is not None
        if row["kind"] in ("order.create", "payment.confirm"):
            valid = valid and command["branch_id"] == row["branch_id"]
        if row["kind"] == "payment.confirm" and binding:
            valid = valid and binding["order_id"] == row["target_id"]
        if row["kind"] == "cash.shift.open" and binding:
            valid = valid and binding["cashier_user_id"] == row["actor_user_id"]
        if row["kind"] in ("cash.shift.close", "cash.shift.close.register") and binding:
            valid = (
                valid
                and binding["cash_shift_id"] == command["cash_shift_id"]
                and (binding["closed_by_user_id"] == row["actor_user_id"])
            )
            shift = (
                session.execute(
                    sa.select(models.cash_shifts.c.id).where(
                        models.cash_shifts.c.id == command["cash_shift_id"],
                        models.cash_shifts.c.organization_id == row["organization_id"],
                        models.cash_shifts.c.branch_id == row["branch_id"],
                    )
                )
                .mappings()
                .first()
            )
            valid = valid and shift is not None
        if row["kind"] == "cash.movement.compensate" and binding:
            valid = valid and _compensation_matches(session, row, resource_id)
        if row["state"] in ("applied", "acknowledged"):
            valid = valid and (
                command["id"] == row["domain_command_id"]
                and command["request_hash"] == row["domain_request_hash"]
                and resource_id == row["resource_id"]
            )
    if not valid or not command:
        raise ops.BusinessError(
            "operational_command_evidence_conflict", "Command evidence requires review"
        )
    return {
        "domain_command_id": command["id"],
        "domain_request_hash": command["request_hash"],
        "resource_id": resource_id,
    }


def _compensation_matches(session: Session, row: Mapping[str, Any], resource_id: str) -> bool:
    original, reversal = (
        models.cash_movements.alias("original"),
        models.cash_movements.alias("reversal"),
    )
    # Verify exact monetary equality inside SQL, returning only a boolean, not amounts.
    return bool(
        session.scalar(
            sa.select(
                sa.exists(
                    sa.select(reversal.c.id).where(
                        original.c.id == row["target_id"],
                        original.c.organization_id == row["organization_id"],
                        original.c.branch_id == row["branch_id"],
                        reversal.c.id == resource_id,
                        reversal.c.organization_id == original.c.organization_id,
                        reversal.c.branch_id == original.c.branch_id,
                        reversal.c.compensates_movement_id == original.c.id,
                        reversal.c.reversal_of_id == original.c.id,
                        reversal.c.amount_cents == original.c.amount_cents,
                        sa.or_(
                            sa.and_(
                                original.c.movement_type == "deposit",
                                reversal.c.movement_type == "withdrawal",
                            ),
                            sa.and_(
                                original.c.movement_type == "withdrawal",
                                reversal.c.movement_type == "deposit",
                            ),
                        ),
                        original.c.status == "confirmed",
                        reversal.c.status == "confirmed",
                        reversal.c.actor_user_id == row["actor_user_id"],
                        reversal.c.cash_shift_id == original.c.cash_shift_id,
                    )
                )
            )
        )
    )


def _audit(session: Session, actor: str, row: Mapping[str, Any], state: str) -> None:
    ops._audit(
        session,
        "operational_command." + state,
        "operational_intent",
        str(row["id"]),
        {"kind": row["kind"], "state": state},
        str(row["branch_id"]),
        actor_user_id=actor,
    )


def prepare_intent(
    session: Session, actor: str, payload: dict[str, Any], key: str | None, secret: str | None
) -> dict[str, Any]:
    with _unit(session):
        if set(payload) != {"kind", "target_id", "payload"} or not isinstance(
            payload["payload"], dict
        ):
            raise ops.BusinessError("operational_command_payload_invalid", "Preparation is invalid")
        kind, target, body = payload["kind"], payload["target_id"], payload["payload"]
        key, digest = _identity(kind, target, body, key)
        _lock(session, actor)
        context = _authority(session, actor, kind, target, body, secret)
        revision = _read_authority(session, actor, kind, str(context["branch_id"]))
        table = models.operational_command_intents
        old_mapping = (
            session.execute(
                sa.select(table).where(
                    table.c.organization_id == ops.ORGANIZATION_ID,
                    table.c.command_namespace == command_namespace(kind),
                    table.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )
        if old_mapping:
            old = dict(old_mapping)
            if (
                old["actor_user_id"] != actor
                or old["request_hash"] != digest
                or old["context_id"] != context["id"]
                or old["authorization_version"] != context["authorization_version"]
            ):
                raise ops.BusinessError("idempotency_conflict", "Command identity already exists")
            if old["state"] in ("applied", "acknowledged"):
                _proof(session, old)
            session.commit()
            _revalidate_read(session, actor, old, revision)
            return _receipt(old)
        now = authority_now()
        row = {
            "id": ops._id(),
            "organization_id": ops.ORGANIZATION_ID,
            "actor_user_id": actor,
            "branch_id": context["branch_id"],
            "context_id": context["id"],
            "authorization_version": context["authorization_version"],
            "kind": kind,
            "command_namespace": command_namespace(kind),
            "target_id": target,
            "idempotency_key": key,
            "request_hash": digest,
            "state": "prepared",
            "domain_command_id": None,
            "domain_request_hash": None,
            "resource_id": None,
            "created_at": now,
            "updated_at": now,
        }
        if _command(session, row):
            raise ops.BusinessError(
                "operational_command_legacy_recovery_required",
                "Recover the existing domain command",
            )
        session.execute(table.insert().values(**row))
        _audit(session, actor, row, "prepared")
        session.commit()
        _revalidate_read(session, actor, row, revision)
        return _receipt(row)


def _owned(session: Session, actor: str, intent_id: str) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(models.operational_command_intents)
            .where(
                models.operational_command_intents.c.organization_id == ops.ORGANIZATION_ID,
                models.operational_command_intents.c.actor_user_id == actor,
                models.operational_command_intents.c.id == _uuid(intent_id),
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not row:
        raise ops.NotFoundError("operational_command_not_found", "Command was not found")
    return dict(row)


@contextmanager
def _atomic_domain(session: Session) -> Iterator[None]:
    rolled_back = False

    def prevent_commit(_: Session) -> None:
        raise ops.BusinessError(
            "operational_command_atomicity_violation",
            "Domain command must participate in the intent transaction",
        )

    def track_rollback(_: Session) -> None:
        nonlocal rolled_back
        rolled_back = True

    sa.event.listen(session, "before_commit", prevent_commit)
    sa.event.listen(session, "after_rollback", track_rollback)
    try:
        yield
        if rolled_back:
            raise ops.BusinessError(
                "operational_command_atomicity_violation",
                "Domain command discarded the intent transaction",
            )
    finally:
        sa.event.remove(session, "before_commit", prevent_commit)
        sa.event.remove(session, "after_rollback", track_rollback)


def execute_intent(
    session: Session,
    actor: str,
    intent_id: str | None,
    kind: str,
    target: str | None,
    body: dict[str, Any],
    key: str | None,
    secret: str | None,
    execute: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    # Domain denial auditing must not discard the actor fence or commit a partial effect.
    try:
        with defer_authorization_audit(central_owner=True) as denials:
            return _execute_intent(
                session, actor, intent_id, kind, target, body, key, secret, execute
            )
    except ops.AuthorizationError:
        with _unit(session):
            for denial in denials:
                ops._audit(
                    session,
                    "authorization.denied",
                    "permission",
                    denial["permission_code"],
                    {"permission": denial["permission_code"], "reason": denial["reason"]},
                    branch_id=denial["branch_id"],
                    actor_user_id=denial["actor_user_id"],
                )
            session.commit()
        raise


def _execute_intent(
    session: Session,
    actor: str,
    intent_id: str | None,
    kind: str,
    target: str | None,
    body: dict[str, Any],
    key: str | None,
    secret: str | None,
    execute: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    with _unit(session):
        if not intent_id:
            raise ops.BusinessError(
                "operational_command_required", "Register the command before sending"
            )
        key, digest = _identity(kind, target, body, key)
        _lock(session, actor)
        row = _owned(session, actor, intent_id)
        revision = _read_authority(session, actor, str(row["kind"]), str(row["branch_id"]))
        if row["state"] == "no_effect":
            raise ops.BusinessError(
                "operational_command_terminal", "Command was resolved without effect"
            )
        context = _authority(session, actor, kind, target, body, secret)
        if (
            row["kind"] != kind
            or row["target_id"] != target
            or row["idempotency_key"] != key
            or row["request_hash"] != digest
            or row["context_id"] != context["id"]
            or row["authorization_version"] != context["authorization_version"]
        ):
            raise ops.BusinessError("idempotency_conflict", "Command identity changed")
        if row["state"] in ("applied", "acknowledged"):
            _proof(session, row)
        with _atomic_domain(session):
            result = execute()
            proof = _proof(session, row)
        if row["state"] == "prepared":
            session.execute(
                models.operational_command_intents.update()
                .where(
                    models.operational_command_intents.c.id == row["id"],
                )
                .values(**proof, state="applied", updated_at=authority_now())
            )
            _audit(session, actor, row, "applied")
        session.commit()
        _revalidate_read(session, actor, row, revision)
        if kind.startswith("cash.shift."):
            ops._record_pco004_metric(
                "cash_shift_open_total"
                if kind == "cash.shift.open"
                else "cash_shift_operational_close_total",
                result="success" if row["state"] == "prepared" else "replay",
                branch_id=row["branch_id"],
            )
        return result


def recover_intent(session: Session, actor: str, intent_id: str) -> dict[str, Any]:
    with _unit(session):
        _lock(session, actor)
        row = _owned(session, actor, intent_id)
        revision = _read_authority(session, actor, str(row["kind"]), str(row["branch_id"]))
        if row["state"] in ("applied", "acknowledged"):
            _proof(session, row)
            next_state = "acknowledged"
        else:
            if _command(session, row):
                raise ops.BusinessError(
                    "operational_command_evidence_conflict",
                    "Unconfirmed domain evidence requires review",
                )
            next_state = "no_effect"
        if row["state"] != next_state:
            session.execute(
                models.operational_command_intents.update()
                .where(
                    models.operational_command_intents.c.id == row["id"],
                )
                .values(state=next_state, updated_at=authority_now())
            )
            _audit(session, actor, row, next_state)
            row["state"] = next_state
        session.commit()
        _revalidate_read(session, actor, row, revision)
        return _receipt(row)


def list_pending(session: Session, actor: str) -> list[dict[str, Any]]:
    with _unit(session):
        _lock(session, actor)
        rows = (
            session.execute(
                sa.select(models.operational_command_intents)
                .where(
                    models.operational_command_intents.c.organization_id == ops.ORGANIZATION_ID,
                    models.operational_command_intents.c.actor_user_id == actor,
                    models.operational_command_intents.c.state.in_(("prepared", "applied")),
                )
                .order_by(
                    models.operational_command_intents.c.created_at,
                    models.operational_command_intents.c.id,
                )
                .limit(100)
            )
            .mappings()
            .all()
        )
        scopes = {(str(row["kind"]), str(row["branch_id"])): None for row in rows}
        revisions = {scope: _read_authority(session, actor, *scope) for scope in scopes}
        receipts = [_receipt(dict(row)) for row in rows]
        session.commit()
        for (kind, branch), revision in revisions.items():
            _revalidate_read(session, actor, {"kind": kind, "branch_id": branch}, revision)
        return receipts

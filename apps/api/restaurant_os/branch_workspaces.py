"""Server-owned branch contexts. Persist hashes and lineage, never plaintext secrets."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings


def _schema_required(session: Session) -> None:
    inspector = sa.inspect(session.connection())
    if (
        not inspector.has_table("branch_workspace_sessions")
        or not inspector.has_table("branch_context_reissue_commands")
        or "authorization_version"
        not in {column["name"] for column in inspector.get_columns("users")}
    ):
        raise ops.BusinessError(
            "authorization_migration_required", "Workspace migration is required"
        )


def current_workspace(session: Session, actor: str) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.select(models.branch_workspace_sessions)
            .where(
                models.branch_workspace_sessions.c.organization_id == ops.ORGANIZATION_ID,
                models.branch_workspace_sessions.c.actor_user_id == actor,
                models.branch_workspace_sessions.c.state.in_(("active", "recovery_only")),
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def workspace_projection(
    session: Session,
    actor: str,
    version: int,
    allowed: list[str],
    home: str | None,
) -> tuple[str | None, dict[str, Any]]:
    """GET projection does not insert, rotate or repair workspace rows."""
    _schema_required(session)
    row = (
        session.execute(
            sa.select(models.branch_workspace_sessions).where(
                models.branch_workspace_sessions.c.organization_id == ops.ORGANIZATION_ID,
                models.branch_workspace_sessions.c.actor_user_id == actor,
                models.branch_workspace_sessions.c.state.in_(("active", "recovery_only")),
            )
        )
        .mappings()
        .first()
    )
    valid = bool(row and row["authorization_version"] == version and row["branch_id"] in allowed)
    branch = (
        str(row["branch_id"])
        if row and valid
        else (allowed[0] if len(allowed) == 1 else home if home in allowed else None)
    )
    return branch, {
        "branch_selection_required": branch is None,
        "branch_workspace_context_id": str(row["id"]) if row and valid else None,
        "branch_workspace_context": None,
        "branch_workspace_secret_version": int(row["secret_version"]) if row and valid else None,
        "branch_workspace_state": str(row["state"]) if row and valid else None,
        "branch_context_reissue_required": branch is not None,
    }


def _lock_actor(session: Session, actor: str) -> None:
    row = (
        session.execute(
            sa.select(models.users.c.id, models.users.c.status)
            .where(
                models.users.c.organization_id == ops.ORGANIZATION_ID,
                models.users.c.id == actor,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not row or row["status"] != "active":
        raise ops.AuthorizationError("actor_not_authorized", "Actor is not authorized")


def _command_authority(session: Session, actor: str, expected: object) -> dict[str, Any]:
    if not get_settings().branch_scope_v2_enabled:
        raise ops.BusinessError("branch_scope_v2_disabled", "Workspace transitions are disabled")
    _schema_required(session)
    ops._authority_governance_lock(session)
    _lock_actor(session, actor)
    if type(expected) is not int or expected < 1:
        raise ops.BusinessError(
            "branch_context_payload_invalid", "Authorization version is required"
        )
    if ops._user_authorization_version(session, actor) != expected:
        raise ops.BusinessError("authorization_version_conflict", "Authorization version changed")
    return ops.build_session_profile(session, actor)


def _key_hash(key: str | None, payload: Mapping[str, Any]) -> tuple[str, str]:
    normalized = str(key or "").strip()
    if not 12 <= len(normalized) <= 180:
        raise ops.BusinessError(
            "idempotency_key_invalid", "Idempotency-Key must contain 12 to 180 characters"
        )
    return normalized, hashlib.sha256(
        json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _uuid(value: object) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError
        return str(UUID(value))
    except ValueError as exc:
        raise ops.BusinessError(
            "branch_context_payload_invalid", "A valid resource ID is required"
        ) from exc


def _new_workspace(
    session: Session,
    actor: str,
    branch: str,
    version: int,
    command_id: str | None,
) -> tuple[str, str, int]:
    old = current_workspace(session, actor)
    if old:
        session.execute(
            models.branch_workspace_sessions.update()
            .where(models.branch_workspace_sessions.c.id == old["id"])
            .values(state="superseded", updated_at=ops._now())
        )
    context_id, secret = ops._id(), secrets.token_urlsafe(48)
    session.execute(
        models.branch_workspace_sessions.insert().values(
            id=context_id,
            organization_id=ops.ORGANIZATION_ID,
            actor_user_id=actor,
            branch_id=branch,
            authorization_version=version,
            token_hash=_secret_hash(secret),
            secret_version=1,
            state="active",
            selection_command_id=command_id,
            created_at=ops._now(),
            updated_at=ops._now(),
        )
    )
    return context_id, secret, 1


def _secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _assert_no_open_shift(session: Session, actor: str) -> None:
    if session.scalar(
        sa.select(models.cash_shifts.c.id)
        .where(
            models.cash_shifts.c.organization_id == ops.ORGANIZATION_ID,
            models.cash_shifts.c.cashier_user_id == actor,
            sa.func.upper(models.cash_shifts.c.status).in_(("OPEN", "CLOSING")),
        )
        .limit(1)
    ):
        raise ops.BusinessError(
            "branch_switch_open_shift", "Close the active cash shift before changing branch"
        )


def _rotate(session: Session, row: Mapping[str, Any]) -> tuple[str, str, int]:
    version = int(row["secret_version"]) + 1
    if version > 2147483647:
        raise ops.BusinessError(
            "branch_context_version_exhausted", "Context version cannot be advanced"
        )
    secret = secrets.token_urlsafe(48)
    session.execute(
        models.branch_workspace_sessions.update()
        .where(models.branch_workspace_sessions.c.id == row["id"])
        .values(token_hash=_secret_hash(secret), secret_version=version, updated_at=ops._now())
    )
    return str(row["id"]), secret, version


def _issued_profile(
    session: Session,
    actor: str,
    issued: tuple[str, str, int],
) -> dict[str, Any]:
    profile = ops.build_session_profile(session, actor)
    profile.update(
        branch_workspace_context_id=issued[0],
        branch_workspace_context=issued[1],
        branch_workspace_secret_version=issued[2],
        branch_context_reissue_required=False,
    )
    return profile


def _live_result(
    row: Mapping[str, Any] | None,
    context_id: str,
    version: int,
) -> Mapping[str, Any]:
    if (
        not row
        or row["id"] != context_id
        or row["state"] != "active"
        or row["authorization_version"] != version
    ):
        raise ops.BusinessError(
            "idempotent_result_superseded", "The command context is no longer current"
        )
    return row


def reissue_branch_context(
    session: Session,
    actor: str,
    payload: dict[str, Any],
    idempotency_key: str | None,
) -> dict[str, Any]:
    if set(payload) != {"context_id", "expected_authorization_version"}:
        raise ops.BusinessError(
            "branch_context_payload_invalid", "Context reissue payload is invalid"
        )
    key, request_hash = _key_hash(idempotency_key, payload)
    profile = _command_authority(session, actor, payload["expected_authorization_version"])
    version = int(profile["scope"]["authorization_version"])
    old = (
        session.execute(
            sa.select(models.branch_context_reissue_commands).where(
                models.branch_context_reissue_commands.c.organization_id == ops.ORGANIZATION_ID,
                models.branch_context_reissue_commands.c.actor_user_id == actor,
                models.branch_context_reissue_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if old and old["request_hash"] != request_hash:
        raise ops.BusinessError("idempotency_conflict", "Idempotency-Key was already used")
    row = current_workspace(session, actor)
    requested = _uuid(payload["context_id"]) if payload["context_id"] is not None else None
    if old:
        row = dict(_live_result(row, str(old["context_id"]), version))
    elif requested:
        row = dict(_live_result(row, requested, version))
    elif row and row["authorization_version"] == version:
        raise ops.BusinessError(
            "branch_context_already_initialized", "Reissue the current context by ID"
        )

    branch = (
        str(row["branch_id"])
        if row and (old or requested)
        else (str(profile["active_branch"]["id"]) if profile["active_branch"] else None)
    )
    if not branch:
        raise ops.BusinessError(
            "branch_selection_required", "Select an authorized branch explicitly"
        )
    workspace_capabilities = (
        "pos.operate",
        "invoicing.read",
        "invoicing.issue",
        "invoicing.cancel",
        "invoicing.receipt.create",
    )
    if not any(
        ops._actor_has_permission(session, actor, code, branch) for code in workspace_capabilities
    ):
        # Reissuing a context never grants its capabilities; each operation checks its own.
        ops.require_permission(session, actor, "pos.operate", branch)
    if branch not in profile["scope"]["allowed_branch_ids"]:
        raise ops.AuthorizationError("permission_denied", "Branch is not authorized")
    if row and not (old or requested) and row["branch_id"] != branch:
        # A changed authority version must not turn first emission into a branch-switch bypass.
        _assert_no_open_shift(session, actor)
    issued = (
        _rotate(session, row)
        if row and (old or requested)
        else _new_workspace(session, actor, branch, version, None)
    )
    if not old:
        session.execute(
            models.branch_context_reissue_commands.insert().values(
                id=ops._id(),
                organization_id=ops.ORGANIZATION_ID,
                actor_user_id=actor,
                context_id=issued[0],
                idempotency_key=key,
                request_hash=request_hash,
                authorization_version=version,
                created_at=ops._now(),
            )
        )
    ops._audit(
        session,
        action="auth.branch_context_reissued",
        entity_type="branch_workspace",
        entity_id=issued[0],
        payload={"authorization_version": version, "secret_version": issued[2]},
        branch_id=branch,
        actor_user_id=actor,
    )
    result = _issued_profile(session, actor, issued)
    session.commit()
    return result


def select_branch_workspace(
    session: Session,
    actor: str,
    payload: dict[str, Any],
    idempotency_key: str | None,
) -> dict[str, Any]:
    if not get_settings().branch_scope_v2_enabled:
        raise ops.BusinessError("branch_scope_v2_disabled", "Workspace transitions are disabled")
    required = {"target_branch_id", "expected_authorization_version"}
    if set(payload) not in (required, required | {"current_branch_id"}):
        raise ops.BusinessError(
            "branch_selection_payload_invalid", "Branch selection payload is invalid"
        )
    key, request_hash = _key_hash(idempotency_key, payload)
    target = _uuid(payload["target_branch_id"])
    profile = _command_authority(session, actor, payload["expected_authorization_version"])
    version = int(profile["scope"]["authorization_version"])
    if (
        not profile["scope"]["can_select_branch"]
        or target not in profile["scope"]["allowed_branch_ids"]
    ):
        raise ops.AuthorizationError("permission_denied", "Actor cannot select this branch")
    ops.require_permission(session, actor, "pos.branch.select", target)
    ops.require_permission(session, actor, "pos.operate", target)
    old = (
        session.execute(
            sa.select(models.branch_selection_commands).where(
                models.branch_selection_commands.c.organization_id == ops.ORGANIZATION_ID,
                models.branch_selection_commands.c.actor_user_id == actor,
                models.branch_selection_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    row = current_workspace(session, actor)
    if old:
        if old["request_hash"] != request_hash:
            raise ops.BusinessError("idempotency_conflict", "Idempotency-Key was already used")
        context_id = str(old["result"].get("context_id") or "")
        live = _live_result(row, context_id, version)
        result = _issued_profile(session, actor, _rotate(session, live))
        session.commit()
        return result
    source = str(profile["active_branch"]["id"]) if profile["active_branch"] else None
    if "current_branch_id" in payload and payload["current_branch_id"] != source:
        raise ops.BusinessError(
            "branch_context_mismatch", "Source branch is not the canonical workspace"
        )
    _assert_no_open_shift(session, actor)
    command_id = ops._id()
    session.execute(
        models.branch_selection_commands.insert().values(
            id=command_id,
            organization_id=ops.ORGANIZATION_ID,
            actor_user_id=actor,
            source_branch_id=source,
            target_branch_id=target,
            idempotency_key=key,
            request_hash=request_hash,
            authorization_version=version,
            result={},
            created_at=ops._now(),
        )
    )
    issued = _new_workspace(session, actor, target, version, command_id)
    session.execute(
        models.branch_selection_commands.update()
        .where(models.branch_selection_commands.c.id == command_id)
        .values(result={"active_branch_id": target, "context_id": issued[0]})
    )
    ops._audit(
        session,
        action="auth.branch_selected",
        entity_type="branch_selection",
        entity_id=target,
        payload={
            "source_branch_id": source,
            "target_branch_id": target,
            "authorization_version": version,
        },
        branch_id=target,
        actor_user_id=actor,
    )
    result = _issued_profile(session, actor, issued)
    session.commit()
    return result


def validate_branch_context(
    session: Session,
    actor: str,
    branch_id: str,
    secret: str | None,
) -> dict[str, Any]:
    """Canonical fence for scoped routes; authority is checked again in the domain."""
    _schema_required(session)
    # SQLite takes its writer lock before reading; PostgreSQL locks this actor only.
    if session.get_bind().dialect.name == "sqlite":
        ops._authority_governance_lock(session)
    _lock_actor(session, actor)
    if not isinstance(secret, str) or not 32 <= len(secret) <= 128:
        raise ops.AuthorizationError(
            "branch_context_required", "A current branch context is required"
        )
    row = current_workspace(session, actor)
    if not row or not hmac.compare_digest(str(row["token_hash"]), _secret_hash(secret)):
        raise ops.AuthorizationError(
            "branch_context_superseded", "Branch context is no longer current"
        )
    if row["branch_id"] != branch_id:
        raise ops.AuthorizationError(
            "branch_context_mismatch", "Branch does not match the current context"
        )
    if row["authorization_version"] != ops._user_authorization_version(session, actor):
        raise ops.AuthorizationError(
            "authorization_version_conflict", "Authorization version changed"
        )
    if row["state"] != "active":
        raise ops.AuthorizationError(
            "branch_context_recovery_only", "Context permits recovery only"
        )
    if not ops._branch_detail(session, branch_id):
        raise ops.AuthorizationError("permission_denied", "Branch is not authorized")
    return row

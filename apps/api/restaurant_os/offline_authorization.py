"""Canonical actor lock, retained grant identity and conservative offline blockers."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings
from restaurant_os.offline_grants import valid_authorization_version

UTC = timezone.utc
LEGACY_TTL = timedelta(hours=2)


def rollback_reconciliation(session: Session) -> None:
    """A secondary cleanup failure must not expose the original signed SQL parameters."""
    try:
        session.rollback()
    except SQLAlchemyError:
        try:
            session.invalidate()
        except SQLAlchemyError:
            # This narrow, failed-error cleanup still ends in the caller's retryable 503.
            # No success or claim of rollback is inferred from an unavailable connection.
            pass


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def registry_available(session: Session) -> bool:
    inspector = sa.inspect(session.connection())
    return all(
        inspector.has_table(name)
        for name in (
            "offline_authorization_leases",
            "offline_authorization_rollouts",
        )
    )


def lock_reconciliation_actor(session: Session, actor: str, organization: str) -> int | None:
    """Fence authority before branch/aggregate locks; ACKs need no active human permission."""
    if organization != ops.ORGANIZATION_ID:
        raise ops.AuthorizationError("permission_denied", "Organization scope is invalid")
    ops._authority_governance_lock(session, organization)
    columns = {column["name"] for column in sa.inspect(session.connection()).get_columns("users")}
    selected = [models.users.c.id]
    if "authorization_version" in columns:
        selected.append(models.users.c.authorization_version)
    row = session.execute(
        sa.select(*selected).where(
            models.users.c.id == actor, models.users.c.organization_id == organization,
        ).with_for_update(key_share=True)
    ).mappings().first()
    if not row:
        return None
    version = row.get("authorization_version")
    return int(version) if valid_authorization_version(version) else None


def reconciliation_authority_error(
    session: Session, *, actor: str, branch: str, kind: str, token: str,
    device_id: str, current_version: int | None, signed_version: int | None,
    bundle_id: str | None = None, epoch: int | None = None,
) -> str | None:
    """Compare exact retained identity, never adopt unknown historical authority."""
    if not registry_available(session):
        if signed_version is not None or get_settings().branch_scope_v2_enabled:
            return "offline_authorization_registry_required"
        return None
    row = session.execute(
        sa.select(models.offline_authorization_leases).where(
            models.offline_authorization_leases.c.organization_id == ops.ORGANIZATION_ID,
            models.offline_authorization_leases.c.grant_kind == kind,
            models.offline_authorization_leases.c.grant_hash
            == hashlib.sha256(token.encode("utf-8")).hexdigest(),
        ).with_for_update(key_share=True)
    ).mappings().first()
    if row is None:
        return "offline_authorization_unregistered"
    bindings = {
        "actor_user_id": actor, "branch_id": branch, "source_device_id": device_id,
        "bundle_id": bundle_id, "lease_epoch": epoch,
    }
    if any(row[field] != value for field, value in bindings.items()):
        return "offline_authorization_invalid"
    if row["state"] == "revoked" or row["revoked_at"] is not None:
        return "offline_authorization_revoked"
    # Expired leases may prove an acceptance within the separately verified signed window.
    if row["state"] not in ("active", "expired"):
        return "offline_authorization_invalid"
    recorded_version = row["authorization_version"]
    if row["provenance"] != "registered" or not valid_authorization_version(recorded_version):
        return "offline_authorization_version_missing"
    if signed_version is not None and signed_version != recorded_version:
        return "offline_authorization_invalid"
    if not valid_authorization_version(current_version) or current_version != recorded_version:
        return "offline_authorization_version_stale"
    return None


def lock_grant_actor(
    session: Session,
    actor: str,
    organization: str,
    branch: str,
    branch_context: str | None = None,
) -> tuple[int, bool]:
    try:
        return _lock_grant_actor(session, actor, organization, branch, branch_context)
    except ops.AuthorizationError as exc:
        session.rollback()
        audit_actor = session.scalar(
            sa.select(models.users.c.id).where(
                models.users.c.id == actor,
                models.users.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        audit_branch = session.scalar(
            sa.select(models.branches.c.id).where(
                models.branches.c.id == branch,
                models.branches.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        ops._record_authorization_denied(
            session,
            actor_user_id=audit_actor,
            branch_id=audit_branch,
            permission_code="offline.grant",
            reason=exc.code,
        )
        raise


def _lock_grant_actor(
    session: Session,
    actor: str,
    organization: str,
    branch: str,
    branch_context: str | None,
) -> tuple[int, bool]:
    if organization != ops.ORGANIZATION_ID:
        raise ops.AuthorizationError("permission_denied", "Organization scope is invalid")
    available = registry_available(session)
    if get_settings().signed_offline_authority_enabled and not available:
        raise ops.BusinessError(
            "offline_authorization_registry_required", "Offline authority migration is required",
        )
    if get_settings().branch_scope_v2_enabled and not available:
        raise ops.BusinessError(
            "branch_offline_preflight_required", "Offline authority migration is required"
        )
    ops._authority_governance_lock(session)
    from restaurant_os.branch_workspaces import _lock_actor, validate_branch_context

    _lock_actor(session, actor)
    if get_settings().branch_scope_v2_enabled:
        validate_branch_context(session, actor, branch, branch_context)
    branch_row = session.scalar(
        sa.select(models.branches.c.id)
        .where(
            models.branches.c.organization_id == organization,
            models.branches.c.id == branch,
            models.branches.c.status == "active",
        )
        .with_for_update(key_share=True)
    )
    if not branch_row:
        raise ops.AuthorizationError("permission_denied", "Branch is not authorized")
    return ops._user_authorization_version(session, actor), available


def existing_grant(
    session: Session,
    *,
    actor: str,
    branch: str,
    kind: str,
    token: str,
    version: int,
    device_id: str,
    bundle_id: str | None = None,
    epoch: int | None = None,
) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.select(models.offline_authorization_leases).where(
                models.offline_authorization_leases.c.organization_id == ops.ORGANIZATION_ID,
                models.offline_authorization_leases.c.grant_kind == kind,
                models.offline_authorization_leases.c.grant_hash
                == hashlib.sha256(token.encode("ascii")).hexdigest(),
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    expected = {
        "actor_user_id": actor,
        "branch_id": branch,
        "authorization_version": version,
        "source_device_id": device_id,
        "bundle_id": bundle_id,
        "lease_epoch": epoch,
        "provenance": "registered",
        "state": "active",
    }
    if any(row[key] != value for key, value in expected.items()):
        raise ops.BusinessError(
            "offline_grant_identity_conflict",
            "Grant identity already has different authority evidence",
        )
    return dict(row)


def register_grant(
    session: Session,
    *,
    actor: str,
    branch: str,
    kind: str,
    token: str,
    version: int,
    device_id: str,
    issued_at: datetime,
    expires_at: datetime,
    bundle_id: str | None = None,
    epoch: int | None = None,
    source_grant_id: str | None = None,
) -> str:
    old = existing_grant(
        session,
        actor=actor,
        branch=branch,
        kind=kind,
        token=token,
        version=version,
        device_id=device_id,
        bundle_id=bundle_id,
        epoch=epoch,
    )
    if old:
        return str(old["id"])
    issued_at, expires_at = _utc(issued_at), _utc(expires_at)
    if expires_at < issued_at or expires_at > issued_at + LEGACY_TTL:
        raise ops.BusinessError(
            "offline_grant_interval_invalid", "Grant interval exceeds offline authority limits"
        )
    lease_id = ops._id()
    session.execute(
        models.offline_authorization_leases.insert().values(
            id=lease_id,
            organization_id=ops.ORGANIZATION_ID,
            actor_user_id=actor,
            branch_id=branch,
            grant_kind=kind,
            grant_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            authorization_version=version,
            provenance="registered",
            source_device_id=device_id,
            bundle_id=bundle_id,
            lease_epoch=epoch,
            source_grant_id=source_grant_id,
            issued_at=issued_at,
            expires_at=expires_at,
            state="active",
            revoked_at=None,
        )
    )
    ops._audit(
        session,
        action="auth.offline_grant_registered",
        entity_type="offline_authorization_lease",
        entity_id=lease_id,
        branch_id=branch,
        actor_user_id=actor,
        payload={
            "grant_kind": kind,
            "authorization_version": version,
            "source_device_id": device_id,
            "bundle_id": bundle_id,
            "expires_at": expires_at.isoformat(),
        },
    )
    return lease_id


def assert_transition_allowed(session: Session, actor: str, target_branch: str) -> None:
    if not registry_available(session):
        raise ops.BusinessError(
            "branch_offline_preflight_required", "Offline authority migration is required"
        )
    # Signed grants validate inclusive integer seconds. Keep the final valid second blocked.
    now = datetime.fromtimestamp(int(ops._now().timestamp()), UTC)
    rollout = (
        session.execute(
            sa.select(models.offline_authorization_rollouts)
            .where(
                models.offline_authorization_rollouts.c.organization_id == ops.ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not rollout or rollout["state"] == "unprepared":
        raise ops.BusinessError(
            "branch_offline_preflight_required", "Offline issuer cutover is not prepared"
        )
    started, drained = rollout["registration_started_at"], rollout["legacy_drain_until"]
    if not started or not drained:
        raise ops.BusinessError(
            "branch_offline_preflight_required", "Offline issuer cutover evidence is incomplete"
        )
    started, drained = _utc(started), _utc(drained)
    if (
        (rollout["state"] == "draining" and drained < started + LEGACY_TTL)
        or (rollout["state"] == "clean_install" and drained != started)
        or now <= drained
    ):
        raise ops.BusinessError(
            "branch_offline_preflight_required", "Legacy offline grants have not drained"
        )
    untracked = session.scalar(
        sa.select(models.offline_order_grants.c.id)
        .select_from(
            models.offline_order_grants.outerjoin(
                models.offline_authorization_leases,
                sa.and_(
                    models.offline_authorization_leases.c.source_grant_id
                    == models.offline_order_grants.c.id,
                    models.offline_authorization_leases.c.organization_id
                    == models.offline_order_grants.c.organization_id,
                ),
            )
        )
        .where(
            models.offline_order_grants.c.organization_id == ops.ORGANIZATION_ID,
            models.offline_order_grants.c.expires_at >= now,
            models.offline_authorization_leases.c.id.is_(None),
        )
        .limit(1)
    )
    if untracked:
        raise ops.BusinessError(
            "branch_offline_preflight_required", "Unregistered retained offline grants remain live"
        )
    if session.scalar(
        sa.select(models.offline_authorization_leases.c.id)
        .where(
            models.offline_authorization_leases.c.organization_id == ops.ORGANIZATION_ID,
            models.offline_authorization_leases.c.actor_user_id == actor,
            models.offline_authorization_leases.c.branch_id != target_branch,
            models.offline_authorization_leases.c.expires_at >= now,
        )
        .limit(1)
    ):
        raise ops.BusinessError(
            "branch_switch_offline_grant", "Wait for incompatible offline authority to expire"
        )

"""Fiscal permissions are checked against actual organization/branch resources."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings

from .documents import document_available


def require_configuration_permission(
    session: Session, actor: str | None, *, lock_for_write: bool = False
) -> str:
    actor_id = actor or ""
    if lock_for_write:
        ops._authority_governance_lock(session)
        session.execute(
            sa.select(models.users.c.id)
            .where(
                models.users.c.id == actor_id,
                models.users.c.organization_id == ops.ORGANIZATION_ID,
            )
            .with_for_update()
        ).scalar_one_or_none()
    ops.require_permission(session, actor_id, "invoicing.config.manage", None)
    if not ops._actor_has_organization_scope(session, actor_id, "invoicing.config.manage"):
        ops._record_authorization_denied(
            session,
            actor_user_id=actor_id,
            permission_code="invoicing.config.manage",
            branch_id=None,
            reason="organization_scope_required",
        )
        raise ops.AuthorizationError("permission_denied", "Corporate fiscal authority is required")
    return actor_id


def require_branch_permission(
    session: Session,
    actor: str | None,
    organization_id: str,
    branch_id: str,
    permission: str,
    branch_context: str | None = None,
) -> str:
    actor_id = actor or ""
    branch = (
        session.scalar(
            sa.select(models.branches.c.id).where(
                models.branches.c.id == branch_id,
                models.branches.c.organization_id == ops.ORGANIZATION_ID,
                models.branches.c.status == "active",
            )
        )
        if organization_id == ops.ORGANIZATION_ID
        else None
    )
    if branch is None:
        # The default denial sink receives only IDs verified to exist in this tenant.
        audit_actor = session.scalar(
            sa.select(models.users.c.id).where(
                models.users.c.id == actor_id,
                models.users.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        ops._record_authorization_denied(
            session,
            actor_user_id=audit_actor,
            permission_code=permission,
            branch_id=None,
            reason="invalid_branch_scope",
        )
        raise ops.AuthorizationError("permission_denied", "Fiscal branch is not authorized")
    ops.require_permission(session, actor_id, permission, branch_id)
    if get_settings().branch_scope_v2_enabled:
        from restaurant_os.branch_workspaces import validate_branch_context

        try:
            validate_branch_context(session, actor_id, branch_id, branch_context)
        except ops.AuthorizationError as exc:
            ops._record_authorization_denied(
                session,
                actor_user_id=actor_id,
                permission_code=permission,
                branch_id=branch_id,
                reason=exc.code,
            )
            raise
    return actor_id


def authorized_read_branches(
    session: Session,
    actor: str | None,
    organization_id: str,
    requested_branch: str | None,
    branch_context: str | None = None,
) -> list[str]:
    actor_id = actor or ""
    # Validate current actor and existence of the fiscal capability before any document query.
    ops.require_permission(session, actor_id, "invoicing.read", None)
    if organization_id != ops.ORGANIZATION_ID:
        raise ops.AuthorizationError("permission_denied", "Fiscal organization is not authorized")
    if requested_branch:
        require_branch_permission(
            session, actor_id, organization_id, requested_branch, "invoicing.read", branch_context
        )
        return [requested_branch]
    if get_settings().branch_scope_v2_enabled and not ops._actor_has_organization_scope(
        session, actor_id, "invoicing.read"
    ):
        profile = ops.build_session_profile(session, actor_id)
        active = profile["active_branch"]
        if not active:
            raise ops.AuthorizationError("branch_context_required", "Select a branch first")
        require_branch_permission(
            session, actor_id, organization_id, str(active["id"]), "invoicing.read", branch_context
        )
        return [str(active["id"])]
    branches: list[str] = list(
        session.scalars(
            sa.select(models.branches.c.id)
            .where(
                models.branches.c.organization_id == organization_id,
                models.branches.c.status == "active",
            )
            .order_by(models.branches.c.id)
        )
    )
    return [
        str(branch)
        for branch in branches
        if ops._actor_has_permission(session, actor_id, "invoicing.read", str(branch))
    ]


def public_config(config: dict[str, object] | None) -> dict[str, object]:
    value = dict(config or {})
    configured = bool(value.pop("api_key", None))
    value["api_key_configured"] = configured
    return value


def public_invoice(invoice: dict[str, object]) -> dict[str, object]:
    protected = {"raw_sat_response", "verification_url", "self_invoice_url"}
    value = {key: value for key, value in invoice.items() if key not in protected}
    for format in ("pdf", "xml"):
        value[f"{format}_url"] = (
            f"/api/v1/invoicing/invoices/{invoice['id']}/{format}"
            if document_available(invoice)
            else None
        )
    return value

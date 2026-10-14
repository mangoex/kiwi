"""HTTP document writers share the governance/actor fence with workspace transitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.branch_workspaces import validate_branch_context
from restaurant_os.config import get_settings

DocumentKind = Literal["purchase", "expense"]
CONCEPT_COMMANDS = frozenset(("concept.create", "concept.edit", "concept.archive"))


def _branch_context(session: Session, actor: str, branch: str, secret: str | None) -> None:
    try:
        validate_branch_context(session, actor, branch, secret)
    except ops.AuthorizationError as error:
        audit_actor = session.scalar(
            sa.select(models.users.c.id).where(
                models.users.c.id == actor, models.users.c.organization_id == ops.ORGANIZATION_ID
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
            permission_code="branch.workspace",
            branch_id=audit_branch,
            reason=error.code,
        )
        raise


def _document_branch(session: Session, kind: DocumentKind, target: str) -> str:
    table = models.purchase_documents if kind == "purchase" else models.expense_documents
    branch = session.scalar(
        sa.select(table.c.branch_id).where(
            table.c.id == target, table.c.organization_id == ops.ORGANIZATION_ID
        )
    )
    if branch is None:
        raise ops.BusinessError(
            "purchase_not_found" if kind == "purchase" else "expense_not_found",
            "Document was not found in your organization",
        )
    # These domains keep document.branch_id immutable. Lock the actor before their domain locks.
    return str(branch)


def require_document_context(
    session: Session,
    actor: str,
    secret: str | None,
    kind: DocumentKind,
    *,
    branch_id: object = None,
    target_id: str | None = None,
) -> None:
    if not get_settings().branch_scope_v2_enabled:
        return
    ops._authority_governance_lock(session)
    branch = _document_branch(session, kind, target_id) if target_id else str(branch_id or "")
    _branch_context(session, actor, branch, secret)


def require_expense_resolution_context(
    session: Session, actor: str, secret: str | None, key: str, body: Mapping[str, Any]
) -> None:
    if not get_settings().branch_scope_v2_enabled:
        return
    ops._authority_governance_lock(session)
    record = (
        session.execute(
            sa.select(
                models.expense_commands.c.command_type, models.expense_commands.c.branch_id
            ).where(
                models.expense_commands.c.organization_id == ops.ORGANIZATION_ID,
                models.expense_commands.c.actor_user_id == actor,
                models.expense_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if record:
        if record["command_type"] in CONCEPT_COMMANDS:
            return
        branch = str(record["branch_id"] or "")
    else:
        kind = body.get("kind")
        if isinstance(kind, str) and kind in CONCEPT_COMMANDS:
            return
        target = body.get("target_id")
        branch = (
            _document_branch(session, "expense", str(target))
            if target
            else str(body.get("branch_id") or "")
        )
    _branch_context(session, actor, branch, secret)

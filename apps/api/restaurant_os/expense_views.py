"""Expense read authority and own-command receipts, separate from immutable results."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock
from restaurant_os.financial_reads import require_financial_read


class ExpenseOperationalRecord(FinancialRecord):
    id: str
    branch_id: str
    concept_id: str
    document_date: date
    payment_method: Literal["cash", "transfer", "card", "other"]
    status: Literal["draft", "confirmed", "cancelled"]
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class ExpenseOperationalPageV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    items: list[ExpenseOperationalRecord]
    next_cursor: str | None


class ExpenseConceptSnapshot(FinancialRecord):
    code: str
    name: str


class ExpenseDraftV2(ExpenseOperationalRecord):
    schema_version: Literal[2] = 2
    projection: Literal["own_operation"] = "own_operation"
    policy_version: int
    folio: str
    total_cents: int
    tax_cents: int | None
    currency: Literal["MXN"]
    concept_snapshot: ExpenseConceptSnapshot
    reference: str
    notes: str
    evidence_refs: list[str]


class ExpenseCommandReceiptV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    policy_version: int
    command_id: str
    id: str
    branch_id: str
    action: Literal["document.create", "document.edit", "document.confirm", "document.cancel"]
    status: Literal["draft", "confirmed", "cancelled", "abandoned"]
    version: int | None
    accepted_at: datetime


def require_read(session: Session, actor: str, branch: str) -> int | None:
    governance_lock(session, ops.ORGANIZATION_ID)
    if active_revision(session, branch) is None:
        return None
    revision = FinancialAuthority(session, actor, ops.ORGANIZATION_ID).policy_revision(branch)
    ops.authorize_branch_scope(session, actor, "expenses.read", branch)
    return revision


def metadata(session: Session, key: str) -> dict[str, Any] | None:
    table = models.expense_commands
    row = (
        session.execute(
            sa.select(
                *(column for column in table.c if column.name != "result"),
                table.c.result["status"].as_string().label("result_status"),
                table.c.result["version"].as_integer().label("result_version"),
            ).where(table.c.organization_id == ops.ORGANIZATION_ID, table.c.idempotency_key == key)
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def document_branch(session: Session, target: str) -> str:
    branch = session.scalar(
        sa.select(models.expense_documents.c.branch_id).where(
            models.expense_documents.c.organization_id == ops.ORGANIZATION_ID,
            models.expense_documents.c.id == target,
        )
    )
    if branch is None:
        raise ops.BusinessError("expense_not_found", "Document was not found")
    return str(branch)


def receipt(session: Session, actor: str, stored: dict[str, Any], revision: int) -> dict[str, Any]:
    branch = str(stored["branch_id"])
    if stored["actor_user_id"] != actor or stored["organization_id"] != ops.ORGANIZATION_ID:
        deny()
    abandoned = stored["request_hash"] == "abandoned"
    result = ExpenseCommandReceiptV2.model_validate(
        {
            "policy_version": revision,
            "command_id": stored["id"],
            "id": stored["target_id"],
            "branch_id": branch,
            "action": stored["command_type"],
            "status": "abandoned" if abandoned else stored["result_status"],
            "version": None if abandoned else stored["result_version"],
            "accepted_at": stored["created_at"],
        }
    ).model_dump(mode="json")
    ops._audit(
        session,
        "expense.receipt_read",
        "expense_command",
        stored["id"],
        {"action": stored["command_type"], "policy_version": revision},
        branch_id=branch,
        actor_user_id=actor,
    )
    session.commit()
    if require_read(session, actor, branch) != revision:
        raise ops.BusinessError(
            "cash_authorization_changed", "Policy changed during receipt delivery"
        )
    return result


def command(
    session: Session,
    actor: str,
    kind: str,
    target: str | None,
    body: dict[str, Any],
    key: str | None,
    execute: Callable[[bool], dict[str, Any]],
) -> dict[str, Any]:
    from restaurant_os.expenses import command_digest

    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        if not isinstance(key, str) or not 8 <= len(key.strip()) <= 180:
            raise ops.BusinessError("idempotency_key_required", "A valid command key is required")
        key = key.strip()
        ops._acquire_idempotency_lock(session, "expense-command", key)
        stored = metadata(session, key)
        branch = (
            str(stored["branch_id"])
            if stored
            else (document_branch(session, target) if target else str(body.get("branch_id") or ""))
        )
        revision = require_read(session, actor, branch)
        if revision is None:
            result = execute(True)
            if require_read(session, actor, branch) is not None:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Policy changed during receipt delivery"
                )
            return result
        digest = command_digest(actor, kind, target, body)
        if stored is not None:
            if stored["actor_user_id"] != actor:
                deny()
            if stored["command_type"] != kind or stored["request_hash"] != digest:
                raise ops.BusinessError("idempotency_key_conflict", "Command identity changed")
        else:
            execute(False)
            stored = metadata(session, key)
        if stored is None or stored["request_hash"] != digest:
            raise ops.BusinessError("command_result_unavailable", "Command result is unavailable")
        return receipt(session, actor, stored, revision)
    except Exception:
        session.rollback()
        raise


def recover(session: Session, actor: str, key: str) -> dict[str, Any]:
    from restaurant_os import expenses

    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        stored = metadata(session, key)
        if stored is None:
            raise ops.BusinessError("expense_result_pending", "No result is available yet")
        if stored["command_type"].startswith("concept."):
            return expenses._recover_command(session, actor, key)
        revision = require_read(session, actor, str(stored["branch_id"]))
        if revision is None:
            return expenses._recover_command(session, actor, key)
        return receipt(session, actor, stored, revision)
    except Exception:
        session.rollback()
        raise


def resolve(session: Session, actor: str, key: str, body: dict[str, Any]) -> dict[str, Any]:
    from restaurant_os import expenses

    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        expenses.shape(body, {"kind", "target_id", "branch_id"}, {"kind", "target_id", "branch_id"})
        kind = expenses.text_value(body, "kind", 32)
        if not 8 <= len(key) <= 180:
            expenses.invalid("Invalid command key")
        ops._acquire_idempotency_lock(session, "expense-command", key)
        stored = metadata(session, key)
        if kind.startswith("concept.") and (
            stored is None or stored["command_type"].startswith("concept.")
        ):
            return expenses._resolve_command(session, actor, key, body)
        branch = str(stored["branch_id"]) if stored else str(body.get("branch_id") or "")
        revision = require_read(session, actor, branch)
        if revision is None:
            result = expenses._resolve_command(session, actor, key, body)
            if require_read(session, actor, branch) is not None:
                raise ops.BusinessError(
                    "cash_authorization_changed", "Policy changed during receipt delivery"
                )
            return result
        if stored is not None:
            if stored["actor_user_id"] != actor:
                deny()
            target = body.get("target_id")
            if (
                stored["command_type"] != kind
                or branch != body["branch_id"]
                or (kind != "document.create" and target != stored["target_id"])
                or (kind == "document.create" and target is not None)
            ):
                raise ops.BusinessError("idempotency_key_conflict", "Command identity changed")
        else:
            expenses._resolve_command(session, actor, key, body, commit=False)
            stored = metadata(session, key)
        if stored is None:
            raise ops.BusinessError("command_result_unavailable", "Command result is unavailable")
        return receipt(session, actor, stored, revision)
    except Exception:
        session.rollback()
        raise


def _own_draft(session: Session, actor: str, doc: Any, expected_version: int | None) -> bool:
    if doc["status"] != "draft" or expected_version != doc["version"]:
        return False
    if not ops._actor_has_permission(session, actor, "expenses.manage", doc["branch_id"]):
        return False
    commands = models.expense_commands
    return (
        session.scalar(
            sa.select(commands.c.id)
            .where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.target_id == doc["id"],
                commands.c.branch_id == doc["branch_id"],
                commands.c.actor_user_id == actor,
                commands.c.command_type.in_(("document.create", "document.edit")),
                commands.c.result["version"].as_integer() == doc["version"],
                commands.c.request_hash != "abandoned",
            )
            .limit(1)
        )
        is not None
    )


def document(
    session: Session, actor: str, target: str, expected_version: int | None
) -> dict[str, Any]:
    from restaurant_os import expenses

    try:
        governance_lock(session, ops.ORGANIZATION_ID)
        branch = document_branch(session, target)
        revision = require_read(session, actor, branch)
        if revision is None:
            return expenses._get_document(session, actor, target)
        table = models.expense_documents
        doc = (
            session.execute(
                sa.select(table.c.id, table.c.branch_id, table.c.version, table.c.status)
                .where(
                    table.c.organization_id == ops.ORGANIZATION_ID,
                    table.c.id == target,
                )
                .with_for_update(read=True)
            )
            .mappings()
            .one()
        )
        own = _own_draft(session, actor, doc, expected_version)
        if own:
            columns = [table.c[name] for name in ExpenseDraftV2.model_fields if name in table.c]
            raw = dict(
                session.execute(sa.select(*columns).where(table.c.id == target)).mappings().one()
            )
            result = ExpenseDraftV2.model_validate({**raw, "policy_version": revision}).model_dump(
                mode="json"
            )
        else:
            require_financial_read(session, actor, branch, ("expenses",))
            result = expenses._get_document(session, actor, target)
        ops._audit(
            session,
            "expense.document_read",
            "expense_document",
            target,
            {"policy_version": revision, "version": doc["version"]},
            branch_id=branch,
            actor_user_id=actor,
        )
        session.commit()
        if require_read(session, actor, branch) != revision:
            raise ops.BusinessError(
                "cash_authorization_changed", "Policy changed during document delivery"
            )
        if own:
            current = (
                session.execute(
                    sa.select(table.c.id, table.c.branch_id, table.c.version, table.c.status)
                    .where(
                        table.c.id == target,
                        table.c.organization_id == ops.ORGANIZATION_ID,
                    )
                    .with_for_update(read=True)
                )
                .mappings()
                .one()
            )
            if not _own_draft(session, actor, current, expected_version):
                deny()
        else:
            require_financial_read(session, actor, branch, ("expenses",))
        return result
    except Exception:
        session.rollback()
        raise

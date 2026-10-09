"""Expense documents: cash is a conditional effect; inventory is never a dependency."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    ReportingProjectionService,
    _acquire_idempotency_lock,
    _audit,
    _begin_cash_shift_serialization,
    _guard_open_cash_shift,
    _id,
    _now,
    _sanitize_for_json,
    _validate_cash_evidence,
    authorize_branch_scope,
    require_permission,
)

METHODS = {"cash", "transfer", "card", "other"}
# Cash ledger uses PostgreSQL INTEGER. Never accept a document it cannot pay atomically.
MAX_CENTS = 2147483647


def invalid(message: str, code: str = "expense_invalid") -> None:
    raise BusinessError(code, message)


def text_value(body: dict[str, Any], key: str, maximum: int, required: bool = True) -> str:
    value = body.get(key, "")
    if (
        not isinstance(value, str)
        or len(value.strip()) > maximum
        or (required and not value.strip())
    ):
        invalid(f"Revisa el campo {key}.")
    return str(value).strip()


def shape(body: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if set(body) - allowed or required - set(body):
        invalid("Los campos del gasto no corresponden al contrato.")


def row(session: Session, table: sa.Table, identifier: str, lock: bool = False) -> dict[str, Any]:
    query = sa.select(table).where(
        table.c.id == identifier, table.c.organization_id == ORGANIZATION_ID
    )
    value = session.execute(query.with_for_update() if lock else query).mappings().first()
    if value is None:
        invalid("No se encontró el registro en tu organización.", "expense_not_found")
    return dict(value or {})


def view(value: dict[str, Any]) -> dict[str, Any]:
    return dict(
        _sanitize_for_json(
            {
                key: item.isoformat() if isinstance(item, date) else item
                for key, item in value.items()
            }
        )
    )


def version(body: dict[str, Any], current: dict[str, Any]) -> None:
    if type(body.get("version")) is not int or body["version"] != current["version"]:
        invalid("El registro cambió. Vuelve a revisarlo.", "expense_version_conflict")


def concept_list(
    session: Session, actor: str, branch: str, archived: bool = False
) -> list[dict[str, Any]]:
    authorize_branch_scope(session, actor, "expense.concept.read", branch)
    if archived:
        require_permission(session, actor, "expense.concept.manage", branch)
    query = sa.select(models.expense_concepts).where(
        models.expense_concepts.c.organization_id == ORGANIZATION_ID
    )
    if not archived:
        query = query.where(models.expense_concepts.c.status == "active")
    return [
        view(dict(r))
        for r in session.execute(query.order_by(models.expense_concepts.c.code)).mappings()
    ]


def cash_context(
    session: Session, actor: str, branch: str, permission: str = "expenses.manage"
) -> dict[str, Any]:
    authorize_branch_scope(session, actor, permission, branch)
    require_permission(session, actor, "cash.movement.withdraw", branch)
    shifts = (
        session.execute(
            sa.select(models.cash_shifts)
            .where(
                models.cash_shifts.c.organization_id == ORGANIZATION_ID,
                models.cash_shifts.c.branch_id == branch,
                sa.func.upper(models.cash_shifts.c.status) == "OPEN",
            )
            .order_by(models.cash_shifts.c.register_code)
        )
        .mappings()
        .all()
    )
    if len({s["register_code"] for s in shifts}) != len(shifts):
        invalid("La caja tiene más de un turno abierto.", "cash_shift_ambiguous")
    return view(
        {
            "branch_id": branch,
            "open_registers": [
                {
                    "register_id": s["register_code"],
                    "cash_shift_id": s["id"],
                    "opened_at": (
                        s["opened_at"].replace(tzinfo=timezone.utc)
                        if s["opened_at"].tzinfo is None else s["opened_at"]
                    ),
                }
                for s in shifts
            ],
        }
    )


def document_values(
    session: Session, body: dict[str, Any], *, editing: bool = False
) -> dict[str, Any]:
    fields = {
        "branch_id",
        "concept_id",
        "document_date",
        "total_cents",
        "tax_cents",
        "payment_method",
        "reference",
        "notes",
        "evidence_refs",
    }
    shape(body, fields | ({"version"} if editing else set()), fields)
    total, tax = body["total_cents"], body["tax_cents"]
    if type(total) is not int or not 1 <= total <= MAX_CENTS:
        invalid("El importe debe ser positivo y expresado en centavos enteros.")
    if tax is not None and (type(tax) is not int or not 0 <= tax <= total):
        invalid("El impuesto debe estar incluido en el total.")
    method = text_value(body, "payment_method", 16)
    if method not in METHODS:
        invalid("Selecciona Efectivo, Transferencia, Tarjeta u Otro.")
    try:
        raw_date = text_value(body, "document_date", 10)
        document_date = date.fromisoformat(raw_date)
        if document_date.isoformat() != raw_date:
            raise ValueError("Expected YYYY-MM-DD")
    except ValueError as exc:
        raise BusinessError("expense_date_invalid", "Indica una fecha válida.") from exc
    concept = row(session, models.expense_concepts, text_value(body, "concept_id", 36), True)
    if concept["status"] != "active":
        invalid("El concepto está archivado.", "expense_concept_archived")
    evidence = body["evidence_refs"]
    if evidence != []:
        evidence = _validate_cash_evidence(evidence)
    elif not isinstance(evidence, list):
        invalid("La evidencia debe ser una lista.")
    return {
        "concept_id": concept["id"],
        "concept_snapshot": {"code": concept["code"], "name": concept["name"]},
        "document_date": document_date,
        "total_cents": total,
        "tax_cents": tax,
        "currency": "MXN",
        "payment_method": method,
        "reference": text_value(body, "reference", 120, False),
        "notes": text_value(body, "notes", 600, False),
        "evidence_refs": evidence,
    }


def command(
    session: Session,
    actor: str,
    kind: str,
    target: str | None,
    body: dict[str, Any],
    key: str | None,
) -> dict[str, Any]:
    """Lock command then document then concept then shift; all effects share one commit."""
    try:
        _begin_cash_shift_serialization(session)
        if not isinstance(key, str) or not 8 <= len(key.strip()) <= 180:
            invalid("Se requiere una clave de operación válida.", "idempotency_key_required")
        key = str(key).strip()
        _acquire_idempotency_lock(session, "expense-command", key)
        is_concept = kind.startswith("concept.")
        table = models.expense_concepts if is_concept else models.expense_documents
        current = row(session, table, target, True) if target else None
        branch = None if is_concept else text_value(body, "branch_id", 36)
        permission = "expense.concept.manage" if is_concept else "expenses.manage"
        if current and not is_concept:
            if current["branch_id"] != branch:
                invalid("La sucursal no coincide con el gasto.", "expense_scope_mismatch")
            if kind == "document.cancel" and current["confirmed_at"] is not None:
                permission = "expenses.cancel"
        authorize_branch_scope(session, actor, permission, branch)
        if current and not is_concept and current["payment_method"] == "cash":
            if kind == "document.confirm":
                require_permission(session, actor, "cash.movement.withdraw", branch)
            if kind == "document.cancel" and current["confirmed_at"] is not None:
                require_permission(session, actor, "cash.movement.compensate", branch)
        digest = hashlib.sha256(
            json.dumps(
                {"actor": actor, "kind": kind, "target": target, "body": body},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        previous = (
            session.execute(
                sa.select(models.expense_commands).where(
                    models.expense_commands.c.organization_id == ORGANIZATION_ID,
                    models.expense_commands.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest:
                invalid("La clave pertenece a otra operación.", "idempotency_key_conflict")
            result = dict(previous["result"])
            session.commit()
            return result
        now = _now()
        identifier = target or _id()
        if is_concept:
            allowed = (
                {"code", "name", "description"}
                if current is None
                else {"version", "name", "description"}
            )
            if kind == "concept.archive":
                allowed = {"version"}
            shape(body, allowed, allowed)
            if current:
                version(body, current)
                if current["status"] != "active":
                    invalid("El concepto está archivado.")
            values = {"updated_at": now, "version": int(current["version"]) + 1 if current else 1}
            if kind == "concept.archive":
                values["status"] = "archived"
            else:
                values.update(
                    name=text_value(body, "name", 160),
                    description=text_value(body, "description", 600, False),
                )
            if current is None:
                values.update(
                    id=identifier,
                    organization_id=ORGANIZATION_ID,
                    code=text_value(body, "code", 64).upper(),
                    status="active",
                    created_by=actor,
                    created_at=now,
                )
        elif kind in {"document.create", "document.edit"}:
            if current:
                version(body, current)
                if current["status"] != "draft":
                    invalid("Sólo se pueden editar borradores.")
            values = document_values(session, body, editing=current is not None)
            values.update(updated_at=now, version=int(current["version"]) + 1 if current else 1)
            if current is None:
                values.update(
                    id=identifier,
                    organization_id=ORGANIZATION_ID,
                    branch_id=branch,
                    folio="GAS-" + identifier,
                    status="draft",
                    created_by=actor,
                    created_at=now,
                )
        else:
            if current is None:
                invalid("No se encontró el gasto.")
            assert current is not None
            version(body, current)
            values = {"version": current["version"] + 1, "updated_at": now}
            if kind == "document.confirm":
                allowed = {"branch_id", "version"}
                if current["payment_method"] == "cash":
                    allowed |= {"register_id", "expected_cash_shift_id"}
                shape(body, allowed, allowed)
                if current["status"] != "draft":
                    invalid("El gasto ya no es un borrador.", "expense_not_confirmable")
                concept = row(session, models.expense_concepts, current["concept_id"], True)
                if concept["status"] != "active":
                    invalid("El concepto está archivado.", "expense_concept_archived")
                if not current["reference"]:
                    invalid("Agrega una referencia antes de confirmar.")
                if current["payment_method"] == "cash":
                    _validate_cash_evidence(current["evidence_refs"])
                    shift = _guard_open_cash_shift(
                        session, text_value(body, "register_id", 32), str(branch)
                    )
                    if shift["id"] != text_value(body, "expected_cash_shift_id", 36):
                        invalid(
                            "El turno cambió. Vuelve a revisar la caja.",
                            "expense_cash_context_changed",
                        )
                    values["cash_movement_id"] = movement(
                        session,
                        actor,
                        {
                            **current,
                            "concept_snapshot": {"code": concept["code"], "name": concept["name"]},
                        },
                        shift["id"],
                        key,
                    )
                values.update(
                    status="confirmed",
                    confirmed_by=actor,
                    confirmed_at=now,
                    concept_snapshot={"code": concept["code"], "name": concept["name"]},
                )
            elif kind == "document.cancel":
                shape(
                    body,
                    {"branch_id", "version", "reason", "cash_returned", "evidence_refs"},
                    {"branch_id", "version", "reason"},
                )
                if current["status"] not in {"draft", "confirmed"}:
                    invalid("El gasto ya está anulado.")
                reason = text_value(body, "reason", 600)
                if current["status"] == "confirmed" and current["payment_method"] == "cash":
                    if body.get("cash_returned") is not True:
                        invalid("Acredita la devolución física antes de anular.")
                    evidence = _validate_cash_evidence(body.get("evidence_refs"))
                    original = row(session, models.cash_movements, current["cash_movement_id"])
                    original_shift = row(session, models.cash_shifts, original["cash_shift_id"])
                    shift = _guard_open_cash_shift(
                        session, original_shift["register_code"], str(branch)
                    )
                    if shift["id"] != original_shift["id"]:
                        invalid("El turno original ya cerró.", "cash_shift_not_open")
                    values["compensation_movement_id"] = movement(
                        session,
                        actor,
                        {**current, "evidence_refs": evidence},
                        shift["id"],
                        key,
                        original["id"],
                    )
                values.update(
                    status="cancelled",
                    cancelled_by=actor,
                    cancelled_at=now,
                    cancellation_reason=reason,
                )
            else:
                invalid("Operación no permitida.")
        if current:
            session.execute(table.update().where(table.c.id == identifier).values(**values))
        else:
            session.execute(table.insert().values(**values))
        result = view(row(session, table, identifier))
        _audit(
            session,
            "expense." + kind,
            table.name,
            identifier,
            {
                "version": result["version"],
                "status": result["status"],
                "cash_movement_id": result.get("cash_movement_id"),
                "compensation_movement_id": result.get("compensation_movement_id"),
                "reason": result.get("cancellation_reason"),
            },
            branch,
            actor_user_id=actor,
        )
        session.execute(
            models.expense_commands.insert().values(
                id=_id(),
                organization_id=ORGANIZATION_ID,
                actor_user_id=actor,
                target_id=identifier,
                branch_id=branch,
                command_type=kind,
                idempotency_key=key,
                request_hash=digest,
                result=result,
                created_at=now,
            )
        )
        session.commit()
        return result
    except IntegrityError as exc:
        session.rollback()
        raise BusinessError(
            "expense_conflict",
            "El registro cambió o el código ya existe. Revisa antes de reintentar.",
        ) from exc
    except Exception:
        session.rollback()
        raise


def movement(
    session: Session,
    actor: str,
    doc: dict[str, Any],
    shift_id: str,
    key: str,
    reversal: str | None = None,
) -> str:
    identifier = _id()
    session.execute(
        models.cash_movements.insert().values(
            id=identifier,
            organization_id=ORGANIZATION_ID,
            branch_id=doc["branch_id"],
            cash_shift_id=shift_id,
            movement_type="deposit" if reversal else "withdrawal",
            amount_cents=doc["total_cents"],
            reason_code="OPERATING_EXPENSE",
            reason="Anulación de gasto" if reversal else "Gasto operativo",
            source_type="EXPENSE_CANCELLATION" if reversal else "EXPENSE",
            source_id=doc["id"],
            actor_user_id=actor,
            idempotency_key=hashlib.sha256(("expense:" + key).encode()).hexdigest(),
            status="confirmed",
            reversal_of_id=reversal,
            compensates_movement_id=reversal,
            concept_snapshot=doc["concept_snapshot"],
            reference=doc["reference"],
            evidence_refs=doc["evidence_refs"],
            created_at=_now(),
        )
    )
    return identifier


def guard_manual_compensation(session: Session, actor: str, identifier: str) -> None:
    """Document-linked cash may only change through its document, including ancestors."""
    seen: set[str] = set()
    pending = [identifier]
    while pending:
        current_id = pending.pop()
        if current_id in seen:
            continue
        seen.add(current_id)
        current = session.execute(
            sa.select(models.cash_movements).where(
                models.cash_movements.c.id == current_id,
                models.cash_movements.c.organization_id == ORGANIZATION_ID,
            )
        ).mappings().first()
        if current is None:
            # The cash domain owns missing movements and incomplete legacy reversals.
            continue
        authorize_branch_scope(session, actor, "cash.movement.compensate", current["branch_id"])
        linked = session.scalar(
            sa.select(models.expense_documents.c.id).where(
                sa.or_(
                    models.expense_documents.c.cash_movement_id == current_id,
                    models.expense_documents.c.compensation_movement_id == current_id,
                )
            )
        )
        if linked or str(current["source_type"] or "").upper() in {
            "EXPENSE",
            "EXPENSE_CANCELLATION",
        }:
            invalid(
                "Anula desde Gastos para conservar la conciliación.", "expense_document_required"
            )
        for field in ("reversal_of_id", "compensates_movement_id"):
            if current[field]:
                pending.append(str(current[field]))


def get_document(session: Session, actor: str, identifier: str) -> dict[str, Any]:
    doc = row(session, models.expense_documents, identifier)
    authorize_branch_scope(session, actor, "expenses.read", doc["branch_id"])
    return view(doc)


def recover_command(session: Session, actor: str, key: str) -> dict[str, Any]:
    record = (
        session.execute(
            sa.select(models.expense_commands).where(
                models.expense_commands.c.organization_id == ORGANIZATION_ID,
                models.expense_commands.c.idempotency_key == key,
                models.expense_commands.c.actor_user_id == actor,
            )
        )
        .mappings()
        .first()
    )
    if record is None:
        invalid(
            "Aún no hay un resultado. Reintenta recuperar o cierra el intento pendiente.",
            "expense_result_pending",
        )
    assert record is not None
    permission = (
        "expense.concept.manage"
        if record["command_type"].startswith("concept.")
        else "expenses.manage"
    )
    if record["command_type"] == "document.cancel" and record["result"].get("confirmed_at"):
        permission = "expenses.cancel"
    authorize_branch_scope(session, actor, permission, record["branch_id"])
    if record["result"].get("payment_method") == "cash" and record["command_type"] in {
        "document.confirm",
        "document.cancel",
    }:
        require_permission(
            session,
            actor,
            "cash.movement.withdraw"
            if record["command_type"] == "document.confirm"
            else "cash.movement.compensate",
            record["branch_id"],
        )
    return dict(record["result"])


def resolve_command(session: Session, actor: str, key: str, body: dict[str, Any]) -> dict[str, Any]:
    """A terminal tombstone fences a late HTTP request; absence alone cannot prove failure."""
    try:
        _begin_cash_shift_serialization(session)
        if not 8 <= len(key) <= 180:
            invalid("Clave inválida.")
        shape(body, {"kind", "target_id", "branch_id"}, {"kind", "target_id", "branch_id"})
        kind = text_value(body, "kind", 32)
        if kind not in {
            "concept.create",
            "concept.edit",
            "concept.archive",
            "document.create",
            "document.edit",
            "document.confirm",
            "document.cancel",
        }:
            invalid("Operación inválida.")
        branch = None if kind.startswith("concept.") else text_value(body, "branch_id", 36)
        permission = "expense.concept.manage" if branch is None else "expenses.manage"
        target = body["target_id"]
        if target:
            current = row(
                session,
                models.expense_concepts if branch is None else models.expense_documents,
                str(target),
            )
            if branch and current["branch_id"] != branch:
                invalid("La sucursal no coincide con el gasto.")
            if kind == "document.cancel" and current["confirmed_at"]:
                permission = "expenses.cancel"
        authorize_branch_scope(session, actor, permission, branch)
        _acquire_idempotency_lock(session, "expense-command", key)
        existing = session.scalar(
            sa.select(models.expense_commands.c.id).where(
                models.expense_commands.c.organization_id == ORGANIZATION_ID,
                models.expense_commands.c.idempotency_key == key,
            )
        )
        if existing:
            result = recover_command(session, actor, key)
        else:
            result = {"abandoned": True}
            identifier = _id()
            session.execute(
                models.expense_commands.insert().values(
                    id=identifier,
                    organization_id=ORGANIZATION_ID,
                    actor_user_id=actor,
                    target_id=str(target or identifier),
                    branch_id=branch,
                    command_type=kind,
                    idempotency_key=key,
                    request_hash="abandoned",
                    result=result,
                    created_at=_now(),
                )
            )
            _audit(
                session,
                "expense.command_abandoned",
                "expense_command",
                identifier,
                {"kind": kind},
                branch,
                actor_user_id=actor,
            )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def local_period(
    session: Session, actor: str, branch: str, from_date: str, to_date: str
) -> tuple[datetime, datetime]:
    authorize_branch_scope(session, actor, "reports.expenses.read", branch)
    zone = session.scalar(
        sa.select(models.branches.c.timezone).where(models.branches.c.id == branch)
    )
    try:
        start = datetime.combine(date.fromisoformat(from_date), time.min, ZoneInfo(str(zone)))
        end = datetime.combine(
            date.fromisoformat(to_date) + timedelta(days=1), time.min, ZoneInfo(str(zone))
        )
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise BusinessError(
            "expense_period_invalid", "Revisa las fechas del periodo y la zona de sucursal."
        ) from exc
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def documents(
    session: Session,
    actor: str,
    branch: str,
    cursor: str | None = None,
    limit: int = 50,
    status: str | None = None,
    concept: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    authorize_branch_scope(session, actor, "expenses.read", branch)
    if not 1 <= limit <= 100:
        invalid("Paginación inválida.")
    binding = hashlib.sha256(
        json.dumps([actor, branch, status, concept, method, limit]).encode()
    ).hexdigest()
    table = models.expense_documents
    query = sa.select(table).where(
        table.c.organization_id == ORGANIZATION_ID, table.c.branch_id == branch
    )
    for column, value in (
        (table.c.status, status),
        (table.c.concept_id, concept),
        (table.c.payment_method, method),
    ):
        if value:
            query = query.where(column == value)
    if cursor:
        try:
            if len(cursor) > 1024:
                raise ValueError
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if decoded["binding"] != binding:
                raise ValueError
            stamp = datetime.fromisoformat(decoded["created_at"])
            identifier = str(decoded["id"])
            query = query.where(
                sa.or_(
                    table.c.created_at < stamp,
                    sa.and_(table.c.created_at == stamp, table.c.id > identifier),
                )
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise BusinessError(
                "expense_cursor_invalid", "El cursor no corresponde a estos filtros."
            ) from exc
    found = (
        session.execute(query.order_by(table.c.created_at.desc(), table.c.id).limit(limit + 1))
        .mappings()
        .all()
    )
    return {
        "items": [view(dict(r)) for r in found[:limit]],
        "next_cursor": base64.urlsafe_b64encode(
            json.dumps(
                {
                    "binding": binding,
                    "created_at": found[limit - 1]["created_at"].isoformat(),
                    "id": found[limit - 1]["id"],
                }
            ).encode()
        ).decode()
        if len(found) > limit
        else None,
    }


def report_events(
    session: Session, start: datetime, end: datetime, branch: str | None
) -> list[dict[str, Any]]:
    table = models.expense_documents
    query = sa.select(table).where(
        table.c.organization_id == ORGANIZATION_ID,
        table.c.confirmed_at.is_not(None),
        sa.or_(
            sa.and_(table.c.confirmed_at >= start, table.c.confirmed_at < end),
            sa.and_(table.c.cancelled_at >= start, table.c.cancelled_at < end),
        ),
    )
    if branch:
        query = query.where(table.c.branch_id == branch)
    result = []
    from restaurant_os.operations import _utc_cursor_datetime

    for doc in session.execute(query).mappings():
        for field, sign, source in (
            ("confirmed_at", 1, "expense"),
            ("cancelled_at", -1, "expense_cancellation"),
        ):
            if doc[field] and start <= _utc_cursor_datetime(doc[field]) < end:
                tax = doc["tax_cents"]
                result.append(
                    {
                        "id": source + ":" + doc["id"],
                        "source": source,
                        "branch_id": doc["branch_id"],
                        "occurred_at": doc[field],
                        "subtotal_cents": sign * (doc["total_cents"] - tax)
                        if tax is not None
                        else None,
                        "discount_cents": 0,
                        "tax_cents": sign * tax if tax is not None else None,
                        "total_cents": sign * doc["total_cents"],
                        "linked_source_id": "expense:" + doc["id"] if sign < 0 else None,
                        "concept_id": doc["concept_id"],
                        "concept_name": doc["concept_snapshot"]["name"],
                        "payment_method": doc["payment_method"],
                    }
                )
    return result


def summary(session: Session, actor: str, raw: dict[str, Any]) -> dict[str, Any]:
    start, end, branch, _ = ReportingProjectionService(session, actor)._pco007_period(
        raw, "reports.expenses.read"
    )
    table = models.expense_documents
    base = [table.c.organization_id == ORGANIZATION_ID, table.c.confirmed_at.is_not(None)]
    if branch:
        base.append(table.c.branch_id == branch)
    for field in ("concept_id", "payment_method"):
        if raw.get(field):
            base.append(table.c[field] == raw[field])
    # Aggregate at the database; summary is independent of the visible document page.
    name = table.c.concept_snapshot["name"].as_string()
    queries = []
    for stamp, sign in ((table.c.confirmed_at, 1), (table.c.cancelled_at, -1)):
        queries.append(
            sa.select(
                table.c.branch_id,
                table.c.concept_id,
                name.label("concept_name"),
                table.c.payment_method,
                (sa.func.sum(table.c.total_cents) * sign).label("net_cents"),
            )
            .where(*base, stamp >= start, stamp < end)
            .group_by(
                table.c.branch_id,
                table.c.concept_id,
                name,
                table.c.payment_method,
            )
        )
    events = session.execute(sa.union_all(*queries)).mappings().all()
    confirmed = sum(int(e["net_cents"]) for e in events if e["net_cents"] > 0)
    reversals = -sum(int(e["net_cents"]) for e in events if e["net_cents"] < 0)
    cash = sum(int(e["net_cents"]) for e in events if e["payment_method"] == "cash")
    grouped: dict[tuple[str, str, str, str], int] = {}
    for e in events:
        key = (e["branch_id"], e["concept_id"], e["concept_name"], e["payment_method"])
        grouped[key] = grouped.get(key, 0) + int(e["net_cents"])
    return {
        "confirmed_cents": confirmed,
        "reversed_cents": reversals,
        "net_cents": confirmed - reversals,
        "cash_cents": cash,
        "other_cents": confirmed - reversals - cash,
        "groups": [
            {
                "branch_id": k[0],
                "concept_id": k[1],
                "concept_name": k[2],
                "payment_method": k[3],
                "net_cents": v,
            }
            for k, v in sorted(grouped.items())
        ],
    }

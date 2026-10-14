"""Private supplier capture; importing an original never receives stock or creates debt."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import timezone
from typing import Any, TypeVar

import sqlalchemy as sa
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.branch_workspaces import _lock_actor
from restaurant_os.config import get_settings
from restaurant_os.supplier_cfdi_identity import capture_supplier_cfdi_identity
from restaurant_os.supplier_xml_crypto import seal_original, unseal_original
from restaurant_os.supplier_xml_parser import MAX_BYTES, SupplierXmlParseError
from restaurant_os.workspace_fences import require_document_context

RowData = Mapping[str, Any] | RowMapping
Result = TypeVar("Result")


def _rollback(session: Session) -> None:
    try:
        session.rollback()
    except SQLAlchemyError:
        # A COMMIT acknowledgement may be lost after the server durably wrote the command.
        session.close()


def _private_operation(session: Session, operation: Callable[[], Result]) -> Result:
    try:
        return operation()
    except SQLAlchemyError:
        _rollback(session)
        raise ops.BusinessError(
            "supplier_xml_persistence_unavailable", "Private evidence is unavailable"
        ) from None
    except Exception:
        _rollback(session)
        raise


class SupplierXmlResultError(ops.BusinessError):
    def __init__(self, code: str, import_id: str | None = None) -> None:
        super().__init__(code, "Supplier XML requires review; original evidence was not replaced")
        self.import_id = import_id


def _schema(session: Session) -> None:
    inspector = sa.inspect(session.connection())
    if any(
        not inspector.has_table(table.name)
        for table in (
            models.supplier_document_imports,
            models.supplier_document_import_conflicts,
            models.supplier_document_import_commands,
        )
    ):
        raise ops.BusinessError(
            "supplier_xml_migration_required", "Apply the supplier XML migration"
        )


def _authorize_capture(
    session: Session, actor: str, branch: str, secret: str | None
) -> Mapping[str, Any]:
    ops._authority_governance_lock(session)
    _lock_actor(session, actor)
    ops.authorize_branch_scope(session, actor, "purchases.manage", branch)
    require_document_context(session, actor, secret, "purchase", branch_id=branch)
    if not get_settings().supplier_xml_imports_enabled:
        raise ops.BusinessError("supplier_xml_disabled", "Supplier XML capture is disabled")
    _schema(session)
    entity = (
        session.execute(
            sa.select(models.legal_entities.c.id, models.legal_entities.c.tax_id)
            .select_from(
                models.branches.join(
                    models.legal_entities,
                    sa.and_(
                        models.branches.c.legal_entity_id == models.legal_entities.c.id,
                        models.branches.c.organization_id
                        == models.legal_entities.c.organization_id,
                    ),
                )
            )
            .where(
                models.branches.c.id == branch,
                models.branches.c.organization_id == ops.ORGANIZATION_ID,
                models.branches.c.status == "active",
                models.legal_entities.c.status == "active",
            )
            .with_for_update(of=[models.branches, models.legal_entities], key_share=True)
        )
        .mappings()
        .first()
    )
    if not entity or not entity["tax_id"]:
        raise ops.BusinessError(
            "xml_receiver_unconfigured", "The branch receiver must be configured"
        )
    return {"id": entity["id"], "tax_id": entity["tax_id"]}


def authorize_capture(
    session: Session, actor: str, branch: str, secret: str | None
) -> Mapping[str, Any]:
    return _private_operation(session, lambda: _authorize_capture(session, actor, branch, secret))


def _require_key(key: str) -> None:
    if (
        not isinstance(key, str)
        or not 1 <= len(key) <= 128
        or key != key.strip()
        or any(ord(char) < 33 or ord(char) > 126 for char in key)
    ):
        raise ops.BusinessError(
            "idempotency_key_required", "A bounded stable ASCII key is required"
        )


def _context(row: RowData, evidence_id: str, digest: str, kind: str) -> str:
    return json.dumps(
        [
            "supplier_xml_original_v1",
            kind,
            ops.ORGANIZATION_ID,
            row["branch_id"],
            row["legal_entity_id"],
            row["id"],
            evidence_id,
            row["declared_uuid"],
            digest,
        ],
        separators=(",", ":"),
    )


def _result(command: RowData) -> dict[str, Any]:
    if command["result_kind"] != "imported":
        raise SupplierXmlResultError(
            "supplier_xml_duplicate"
            if command["result_kind"] == "duplicate"
            else "supplier_xml_hash_conflict",
            str(command["import_id"]),
        )
    return {
        "id": command["import_id"],
        "status": "unverified",
        "capture_profile": "cfdi4_tfd11_identity_v1",
    }


def _capture_original(
    session: Session,
    actor: str,
    branch: str,
    original: bytes,
    key: str,
    secret: str | None,
) -> dict[str, Any]:
    entity = authorize_capture(session, actor, branch, secret)
    if type(original) is not bytes or not 1 <= len(original) <= MAX_BYTES:
        raise ops.BusinessError("xml_size_exceeded", "XML original size is invalid")
    _require_key(key)
    digest = hashlib.sha256(original).hexdigest()
    request_hash = hashlib.sha256(
        json.dumps(["supplier_xml.import", branch, digest]).encode()
    ).hexdigest()
    ops._acquire_idempotency_lock(session, "supplier_xml.command:" + actor, key)
    commands = models.supplier_document_import_commands
    command = (
        session.execute(
            sa.select(commands).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.actor_user_id == actor,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if command:
        if command["request_hash"] != request_hash or command["branch_id"] != branch:
            raise ops.BusinessError(
                "idempotency_key_conflict", "This key belongs to a different command"
            )
        ops._audit(
            session,
            "supplier_xml.replayed",
            "supplier_document_import",
            str(command["import_id"]),
            {"result": command["result_kind"]},
            branch,
            actor_user_id=actor,
        )
        session.commit()
        return _result(command)
    try:
        identity = capture_supplier_cfdi_identity(original, str(entity["tax_id"]))
    except SupplierXmlParseError as error:
        raise ops.BusinessError(str(error), "Supplier XML cannot be captured") from None
    ops._acquire_idempotency_lock(session, "supplier_xml.uuid", identity.uuid)
    imports = models.supplier_document_imports
    row: RowData | None = (
        session.execute(
            sa.select(imports)
            .where(
                imports.c.organization_id == ops.ORGANIZATION_ID,
                imports.c.declared_uuid == identity.uuid,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    kind, conflict_id = "imported", None
    if row:
        if row["branch_id"] != branch:
            raise SupplierXmlResultError("supplier_xml_duplicate")
        if row["legal_entity_id"] != entity["id"]:
            raise SupplierXmlResultError("supplier_xml_entity_conflict", str(row["id"]))
        kind = "duplicate" if row["original_sha256"] == digest else "conflict"
        if kind == "conflict":
            conflicts = models.supplier_document_import_conflicts
            conflict_id = session.scalar(
                sa.select(conflicts.c.id).where(
                    conflicts.c.import_id == row["id"],
                    conflicts.c.organization_id == ops.ORGANIZATION_ID,
                    conflicts.c.branch_id == branch,
                    conflicts.c.original_sha256 == digest,
                )
            )
            if conflict_id is None:
                conflict_id = ops._id()
                try:
                    encrypted = seal_original(
                        original, _context(row, conflict_id, digest, "conflict")
                    )
                except RuntimeError:
                    raise ops.BusinessError(
                        "supplier_xml_crypto_unavailable", "Private evidence is unavailable"
                    ) from None
                session.execute(
                    conflicts.insert().values(
                        id=conflict_id,
                        organization_id=ops.ORGANIZATION_ID,
                        branch_id=branch,
                        actor_user_id=actor,
                        import_id=row["id"],
                        original_sha256=digest,
                        original_size=len(original),
                        original_ciphertext=encrypted,
                        created_at=ops._now(),
                    )
                )
    else:
        values = {
            "id": ops._id(),
            "organization_id": ops.ORGANIZATION_ID,
            "branch_id": branch,
            "legal_entity_id": str(entity["id"]),
            "actor_user_id": actor,
            "declared_uuid": identity.uuid,
            "capture_profile": identity.capture_profile,
            "fiscal_validation": "unverified",
            "original_sha256": digest,
            "original_size": len(original),
            "created_at": ops._now(),
        }
        try:
            encrypted = seal_original(
                original, _context(values, str(values["id"]), digest, "original")
            )
        except RuntimeError:
            raise ops.BusinessError(
                "supplier_xml_crypto_unavailable", "Private evidence is unavailable"
            ) from None
        values["original_ciphertext"] = encrypted
        session.execute(imports.insert().values(**values))
        row = values
    result = {
        "id": ops._id(),
        "organization_id": ops.ORGANIZATION_ID,
        "branch_id": branch,
        "actor_user_id": actor,
        "idempotency_key": key,
        "request_hash": request_hash,
        "import_id": row["id"],
        "conflict_id": conflict_id,
        "result_kind": kind,
        "created_at": ops._now(),
    }
    session.execute(commands.insert().values(**result))
    ops._audit(
        session,
        "supplier_xml.captured",
        "supplier_document_import",
        str(row["id"]),
        {"result": kind, "size": len(original), "command_id": result["id"]},
        branch,
        actor_user_id=actor,
    )
    session.commit()
    return _result(result)


def capture_original(
    session: Session,
    actor: str,
    branch: str,
    original: bytes,
    key: str,
    secret: str | None,
) -> dict[str, Any]:
    return _private_operation(
        session, lambda: _capture_original(session, actor, branch, original, key, secret)
    )


def _resolve_command(session: Session, actor: str, key: str) -> dict[str, Any]:
    ops._authority_governance_lock(session)
    _lock_actor(session, actor)
    _schema(session)
    _require_key(key)
    table = models.supplier_document_import_commands
    command = (
        session.execute(
            sa.select(table).where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.actor_user_id == actor,
                table.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if not command:
        raise ops.BusinessError("supplier_xml_command_not_found", "Command was not found")
    ops.require_permission(session, actor, "purchases.manage", str(command["branch_id"]))
    ops._audit(
        session,
        "supplier_xml.resolved",
        "supplier_document_import",
        str(command["import_id"]),
        {"result": command["result_kind"]},
        str(command["branch_id"]),
        actor_user_id=actor,
    )
    session.commit()
    return _result(command)


def resolve_command(session: Session, actor: str, key: str) -> dict[str, Any]:
    return _private_operation(session, lambda: _resolve_command(session, actor, key))


def _read(session: Session, actor: str, import_id: str) -> RowData:
    ops._authority_governance_lock(session)
    _lock_actor(session, actor)
    _schema(session)
    row = (
        session.execute(
            sa.select(models.supplier_document_imports).where(
                models.supplier_document_imports.c.organization_id == ops.ORGANIZATION_ID,
                models.supplier_document_imports.c.id == import_id,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ops.BusinessError("supplier_xml_not_found", "Supplier evidence was not found")
    # Current grants authorize the immutable historical resource branch.
    ops.require_permission(session, actor, "purchases.read", str(row["branch_id"]))
    return row


def _metadata(session: Session, actor: str, import_id: str) -> dict[str, Any]:
    row = _read(session, actor, import_id)
    created = row["created_at"]
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    result = {
        "id": row["id"],
        "branch_id": row["branch_id"],
        "legal_entity_id": row["legal_entity_id"],
        "status": row["fiscal_validation"],
        "capture_profile": row["capture_profile"],
        "original_size": row["original_size"],
        "created_at": created.astimezone(timezone.utc).isoformat(),
    }
    ops._audit(
        session,
        "supplier_xml.read",
        "supplier_document_import",
        import_id,
        {},
        str(row["branch_id"]),
        actor_user_id=actor,
    )
    session.commit()
    return result


def _download_original(session: Session, actor: str, import_id: str) -> bytes:
    row = _read(session, actor, import_id)
    try:
        original = unseal_original(
            str(row["original_ciphertext"]),
            _context(row, import_id, str(row["original_sha256"]), "original"),
        )
        if (
            len(original) != row["original_size"]
            or hashlib.sha256(original).hexdigest() != row["original_sha256"]
        ):
            raise RuntimeError("original mismatch")
    except RuntimeError:
        raise ops.BusinessError(
            "supplier_xml_crypto_unavailable", "Private evidence is unavailable"
        ) from None
    ops._audit(
        session,
        "supplier_xml.download",
        "supplier_document_import",
        import_id,
        {},
        str(row["branch_id"]),
        actor_user_id=actor,
    )
    session.commit()
    return original


def metadata(session: Session, actor: str, import_id: str) -> dict[str, Any]:
    return _private_operation(session, lambda: _metadata(session, actor, import_id))


def download_original(session: Session, actor: str, import_id: str) -> bytes:
    return _private_operation(session, lambda: _download_original(session, actor, import_id))

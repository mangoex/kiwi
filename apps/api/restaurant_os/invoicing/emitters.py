"""Explicit legal issuer identity and append-only, encrypted configuration revisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID, BusinessError, NotFoundError, _audit

from .authority import require_configuration_permission
from .crypto import seal, unseal
from .facturapi_client import FacturapiClient

TEXT_LIMITS = {
    "environment": 24,
    "organization_legal_name": 200,
    "organization_rfc": 13,
    "organization_tax_system": 10,
    "organization_zip": 10,
    "default_product_sat_key": 16,
    "default_unit_sat_key": 16,
    "series": 10,
    "self_invoicing_domain": 120,
}
FLAGS = {"is_enabled", "enable_self_invoicing", "print_qr_on_ticket"}
CONFIG_FIELDS = set(TEXT_LIMITS) | FLAGS | {"self_invoicing_days_valid", "api_key"}
MAX_VERSION = 2147483647


def _context(org: str, configuration: str, version: int) -> str:
    return f"fiscal:configuration:{org}:{configuration}:{version}"


def _legal_entity(
    session: Session, org: str, identifier: str, *, lock: bool = False
) -> dict[str, Any]:
    if org != ORGANIZATION_ID:
        raise NotFoundError("fiscal_emitter_not_found", "Fiscal emitter not found")
    query = sa.select(models.legal_entities).where(
        models.legal_entities.c.organization_id == org,
        models.legal_entities.c.id == identifier,
        models.legal_entities.c.status == "active",
    )
    if lock:
        query = query.with_for_update()
    row = session.execute(query).mappings().first()
    if row is None:
        raise NotFoundError("fiscal_emitter_not_found", "Fiscal emitter not found")
    return dict(row)


def _identity(
    session: Session, org: str, emitter: str, *, lock: bool = False
) -> dict[str, Any] | None:
    query = sa.select(models.fiscal_emitter_configurations).where(
        models.fiscal_emitter_configurations.c.organization_id == org,
        models.fiscal_emitter_configurations.c.legal_entity_id == emitter,
    )
    if lock:
        query = query.with_for_update()
    row = session.execute(query).mappings().first()
    return dict(row) if row else None


def _revision(session: Session, identity: dict[str, Any], version: int) -> dict[str, Any]:
    encrypted = session.scalar(
        sa.select(models.fiscal_emitter_configuration_versions.c.payload_ciphertext).where(
            models.fiscal_emitter_configuration_versions.c.configuration_id == identity["id"],
            models.fiscal_emitter_configuration_versions.c.version == version,
        )
    )
    if not isinstance(encrypted, str):
        raise RuntimeError("fiscal_configuration_revision_unavailable")
    value = unseal(encrypted, _context(identity["organization_id"], identity["id"], version))
    if set(value) != CONFIG_FIELDS:
        raise RuntimeError("fiscal_configuration_revision_unavailable")
    return {
        **value,
        "id": identity["id"],
        "organization_id": identity["organization_id"],
        "legal_entity_id": identity["legal_entity_id"],
        "version": version,
    }


def _empty(emitter: dict[str, Any]) -> dict[str, Any]:
    return {
        **{field: "" for field in TEXT_LIMITS},
        **{field: False for field in FLAGS},
        "self_invoicing_days_valid": None,
        "api_key": None,
        "id": None,
        "organization_id": emitter["organization_id"],
        "legal_entity_id": emitter["id"],
        "organization_legal_name": emitter["name"],
        "organization_rfc": emitter["tax_id"] or "",
        "version": 0,
    }


def _public(value: dict[str, Any]) -> dict[str, Any]:
    return {
        **{field: value.get(field) for field in CONFIG_FIELDS - {"api_key"}},
        **{
            field: value.get(field)
            for field in ("id", "organization_id", "legal_entity_id", "version")
        },
        "api_key_configured": bool(value.get("api_key")),
    }


def list_emitters(session: Session, actor: str) -> list[dict[str, Any]]:
    require_configuration_permission(session, actor)
    return [
        dict(row)
        for row in session.execute(
            sa.select(
                models.legal_entities.c.id,
                models.legal_entities.c.name,
                models.legal_entities.c.tax_id,
            )
            .where(
                models.legal_entities.c.organization_id == ORGANIZATION_ID,
                models.legal_entities.c.status == "active",
            )
            .order_by(models.legal_entities.c.name, models.legal_entities.c.id)
        ).mappings()
    ]


def read_configuration(session: Session, actor: str, emitter_id: str) -> dict[str, Any]:
    require_configuration_permission(session, actor)
    emitter = _legal_entity(session, ORGANIZATION_ID, emitter_id)
    identity = _identity(session, ORGANIZATION_ID, emitter_id)
    return _public(
        _revision(session, identity, identity["current_version"]) if identity else _empty(emitter)
    )


def _normalize(
    payload: dict[str, Any], previous: dict[str, Any], emitter: dict[str, Any]
) -> dict[str, Any]:
    if set(payload) - (CONFIG_FIELDS | {"expected_version"}):
        raise BusinessError("fiscal_configuration_invalid", "Unexpected configuration field")
    value: dict[str, Any] = {
        field: payload.get(field, previous.get(field)) for field in CONFIG_FIELDS
    }
    for field, limit in TEXT_LIMITS.items():
        if not isinstance(value[field], str) or len(value[field]) > limit:
            raise BusinessError(
                "fiscal_configuration_invalid", "Text configuration field is invalid"
            )
        value[field] = value[field].strip()
    for field in FLAGS:
        if type(value[field]) is not bool:
            raise BusinessError(
                "fiscal_configuration_invalid", "Boolean configuration field is invalid"
            )
    days = value["self_invoicing_days_valid"]
    if days is not None and (type(days) is not int or not 1 <= days <= MAX_VERSION):
        raise BusinessError(
            "fiscal_configuration_invalid", "Receipt validity must be a positive integer"
        )
    credential = value["api_key"]
    if credential is not None and (
        not isinstance(credential, str)
        or len(credential) > 256
        or any(ord(char) < 32 or ord(char) > 126 for char in credential)
    ):
        raise BusinessError("fiscal_configuration_invalid", "Credential is invalid")
    supplied_key = payload.get("api_key")
    if isinstance(credential, str):
        credential = credential.strip()
    if not credential:
        credential = previous.get("api_key")
    value["api_key"] = credential
    environment = value["environment"]
    if environment not in {"", "sandbox", "live"} or (value["is_enabled"] and not environment):
        raise BusinessError("fiscal_configuration_invalid", "Environment is invalid")
    if (
        previous.get("version", 0)
        and environment != previous.get("environment")
        and (not isinstance(supplied_key, str) or not supplied_key.strip())
    ):
        raise BusinessError(
            "fiscal_configuration_invalid", "Environment changes require a new credential"
        )
    if credential and not credential.startswith(
        "sk_test_" if environment == "sandbox" else "sk_live_"
    ):
        raise BusinessError("fiscal_configuration_invalid", "Credential does not match environment")
    value["organization_rfc"] = value["organization_rfc"].upper()
    if value["is_enabled"]:
        required = set(TEXT_LIMITS) - {"self_invoicing_domain"}
        if any(not value[field] for field in required) or not credential:
            raise BusinessError(
                "fiscal_configuration_invalid", "Explicit fiscal fields and credential are required"
            )
        tax_id = emitter.get("tax_id")
        if (
            not isinstance(tax_id, str)
            or not tax_id.strip()
            or value["organization_rfc"] != tax_id.strip().upper()
        ):
            raise BusinessError(
                "fiscal_configuration_invalid", "Fiscal identity differs from the legal entity"
            )
    if value["enable_self_invoicing"] and (not value["self_invoicing_domain"] or days is None):
        raise BusinessError(
            "fiscal_configuration_invalid", "Explicit self-invoicing configuration is required"
        )
    return value


def save_configuration(
    session: Session, actor: str, emitter_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    require_configuration_permission(session, actor, lock_for_write=True)
    try:
        emitter = _legal_entity(session, ORGANIZATION_ID, emitter_id, lock=True)
        identity = _identity(session, ORGANIZATION_ID, emitter_id, lock=True)
        expected = payload.get("expected_version")
        current = identity["current_version"] if identity else 0
        if type(expected) is not int or not 0 <= expected <= MAX_VERSION:
            raise BusinessError(
                "fiscal_configuration_invalid", "Expected version must be an integer"
            )
        if expected != current:
            raise BusinessError(
                "fiscal_configuration_version_conflict", "Fiscal configuration changed"
            )
        if current == MAX_VERSION:
            raise BusinessError(
                "fiscal_configuration_version_conflict", "Fiscal configuration version exhausted"
            )
        previous = _revision(session, identity, current) if identity else _empty(emitter)
        value = _normalize(payload, previous, emitter)
        identifier, version = identity["id"] if identity else str(uuid4()), current + 1
        encrypted = seal(value, _context(ORGANIZATION_ID, identifier, version))
        now = datetime.now(timezone.utc)
        if identity is None:
            session.execute(
                models.fiscal_emitter_configurations.insert().values(
                    id=identifier,
                    organization_id=ORGANIZATION_ID,
                    legal_entity_id=emitter_id,
                    current_version=version,
                    created_at=now,
                    updated_at=now,
                )
            )
        session.execute(
            models.fiscal_emitter_configuration_versions.insert().values(
                id=str(uuid4()),
                configuration_id=identifier,
                version=version,
                payload_ciphertext=encrypted,
                actor_user_id=actor,
                created_at=now,
            )
        )
        if identity:
            session.execute(
                models.fiscal_emitter_configurations.update()
                .where(models.fiscal_emitter_configurations.c.id == identifier)
                .values(current_version=version, updated_at=now)
            )
        _audit(
            session,
            action="invoicing.emitter_configuration.updated",
            entity_type="fiscal_emitter_configuration",
            entity_id=identifier,
            actor_user_id=actor,
            branch_id=None,
            payload={
                "legal_entity_id": emitter_id,
                "version": version,
                "environment": value["environment"],
                "is_enabled": value["is_enabled"],
                "credential_replaced": isinstance(payload.get("api_key"), str)
                and bool(payload["api_key"].strip()),
            },
        )
        session.commit()
        return _public(
            {
                **value,
                "id": identifier,
                "organization_id": ORGANIZATION_ID,
                "legal_entity_id": emitter_id,
                "version": version,
            }
        )
    except Exception:
        session.rollback()
        raise


def configuration_for_branch(session: Session, org: str, branch_id: str) -> dict[str, Any]:
    emitter_id = session.scalar(
        sa.select(models.branches.c.legal_entity_id).where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == org,
            models.branches.c.status == "active",
        )
    )
    if not isinstance(emitter_id, str):
        raise NotFoundError("fiscal_emitter_not_found", "Fiscal emitter not found")
    emitter = _legal_entity(session, org, emitter_id)
    identity = _identity(session, org, emitter_id)
    if not identity:
        raise BusinessError(
            "fiscal_emitter_configuration_required", "Explicit issuer configuration is required"
        )
    value = _revision(session, identity, identity["current_version"])
    if not value["is_enabled"]:
        raise BusinessError("fiscal_integration_disabled", "Fiscal integration is disabled")
    _normalize({}, value, emitter)
    return value


def client_for_configuration(value: dict[str, Any]) -> FacturapiClient:
    key = value.get("api_key")
    if not isinstance(key, str) or not key:
        raise BusinessError("fiscal_configuration_invalid", "Fiscal credential is required")
    client = FacturapiClient(api_key=key, is_mock=False)
    if client.is_mock:
        raise BusinessError(
            "fiscal_configuration_invalid", "Implicit mock configuration is not allowed"
        )
    return client


def configuration_for_document(
    session: Session, org: str, invoice: dict[str, Any]
) -> dict[str, Any] | None:
    """Resolve the persisted issuer revision; never borrow another issuer's credential.

    None denotes an unbound historical document, whose legacy origin is handled separately.
    This read deliberately does not require current emitter activity or enablement: disabling
    new issuance does not destroy access to already issued documents.
    """
    identifier = invoice.get("emitter_configuration_id")
    version = invoice.get("emitter_configuration_version")
    if identifier is None and version is None:
        return None
    if not isinstance(identifier, str) or type(version) is not int or version < 1:
        raise BusinessError("fiscal_document_origin_invalid", "Fiscal issuer origin is invalid")
    row = (
        session.execute(
            sa.select(models.fiscal_emitter_configurations).where(
                models.fiscal_emitter_configurations.c.organization_id == org,
                models.fiscal_emitter_configurations.c.id == identifier,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise BusinessError("fiscal_document_origin_invalid", "Fiscal issuer origin is invalid")
    value = _revision(session, dict(row), version)
    if value["organization_rfc"] != invoice.get("rfc_emisor"):
        raise BusinessError("fiscal_document_origin_invalid", "Fiscal issuer identity differs")
    return value


def test_connection(session: Session, actor: str, emitter_id: str) -> dict[str, Any]:
    require_configuration_permission(session, actor)
    _legal_entity(session, ORGANIZATION_ID, emitter_id)
    identity = _identity(session, ORGANIZATION_ID, emitter_id)
    if not identity:
        raise BusinessError(
            "fiscal_emitter_configuration_required", "Explicit issuer configuration is required"
        )
    value = _revision(session, identity, identity["current_version"])
    client = client_for_configuration(value)
    session.rollback()
    result = client.validate_api_key()
    require_configuration_permission(session, actor)
    _legal_entity(session, ORGANIZATION_ID, emitter_id)
    current = _identity(session, ORGANIZATION_ID, emitter_id)
    if (
        not current
        or current["id"] != identity["id"]
        or current["current_version"] != value["version"]
    ):
        raise BusinessError("fiscal_configuration_version_conflict", "Fiscal configuration changed")
    # Facturapi /organizations/me returns an Organization, not a success envelope.
    # This proves credential connectivity only; it does not certify RFC, CSD or SAT readiness.
    success = (
        isinstance(result, dict)
        and isinstance(result.get("id"), str)
        and bool(result["id"].strip())
        and isinstance(result.get("legal"), dict)
    )
    return {
        "success": success,
        "message": "Conexión con la credencial verificada."
        if success
        else "No se pudo verificar la conexión.",
    }

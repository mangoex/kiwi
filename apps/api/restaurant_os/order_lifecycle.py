"""Explicit gateway authority handoff and same-epoch catalog renewal.

This module only governs the authority boundary.  It never imports gateway
rows or calculated order facts into the central database.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.offline_orders import (
    ORDER_OFFLINE_TTL,
    _public_key,
    _utc,
    bootstrap_order_bundle,
    lock_gateway_branch,
)
from restaurant_os.operations import BusinessError

HANDOFF_SCHEMA = "ord-off-handoff/v1"
HANDOFF_STATUS = "RELEASED"


def canonical_handoff_manifest(manifest: dict[str, Any]) -> bytes:
    """Return the exact device-signed representation, excluding its signature."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def handoff_manifest_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_handoff_manifest(manifest)).hexdigest()


def release_gateway_lease(
    session: Session,
    *,
    manifest: dict[str, Any],
    signature: str,
    now: datetime,
    commit: bool = True,
) -> dict[str, Any]:
    """Release one gateway only after its signed epoch manifest fully reconciles."""
    command = validate_handoff_manifest(manifest)
    if not isinstance(signature, str) or not signature:
        raise BusinessError(
            "offline_handoff_signature_invalid", "Gateway handoff signature is invalid"
        )
    released_at = _utc(now)
    lock_gateway_branch(
        session,
        organization_id=command["organization_id"],
        branch_id=command["branch_id"],
    )
    lease = (
        session.execute(
            sa.select(models.offline_order_gateway_leases)
            .where(
                models.offline_order_gateway_leases.c.branch_id == command["branch_id"],
                models.offline_order_gateway_leases.c.organization_id == command["organization_id"],
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if lease is None or any(
        lease[field] != command[field]
        for field in ("organization_id", "branch_id", "device_id", "lease_epoch")
    ):
        raise BusinessError("offline_handoff_lease_invalid", "Gateway lease does not match handoff")
    _verify_signature(str(lease["public_key"]), command, signature)
    digest = handoff_manifest_hash(command)
    existing = (
        session.execute(
            sa.select(models.offline_order_handoffs)
            .where(models.offline_order_handoffs.c.handoff_id == command["handoff_id"])
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if (
            existing["manifest_hash"] != digest
            or existing["organization_id"] != command["organization_id"]
            or existing["branch_id"] != command["branch_id"]
            or existing["device_id"] != command["device_id"]
            or existing["lease_epoch"] != command["lease_epoch"]
        ):
            raise BusinessError("offline_handoff_idempotency_conflict", "Handoff identity differs")
        return _receipt(dict(existing))
    if lease["status"] != "ACTIVE":
        raise BusinessError("offline_handoff_transition_invalid", "Gateway lease is not active")
    _require_complete_epoch(session, command)
    row = {
        "handoff_id": command["handoff_id"],
        "organization_id": command["organization_id"],
        "branch_id": command["branch_id"],
        "device_id": command["device_id"],
        "public_key": lease["public_key"],
        "lease_epoch": command["lease_epoch"],
        "watermark": command["watermark"],
        "manifest_hash": digest,
        "manifest": command,
        "status": HANDOFF_STATUS,
        "created_at": released_at,
        "released_at": released_at,
    }
    session.execute(models.offline_order_handoffs.insert().values(**row))
    session.execute(
        models.offline_order_gateway_leases.update()
        .where(
            models.offline_order_gateway_leases.c.branch_id == command["branch_id"],
            models.offline_order_gateway_leases.c.organization_id == command["organization_id"],
            models.offline_order_gateway_leases.c.device_id == command["device_id"],
            models.offline_order_gateway_leases.c.lease_epoch == command["lease_epoch"],
            models.offline_order_gateway_leases.c.status == "ACTIVE",
        )
        .values(status=HANDOFF_STATUS)
    )
    released = session.scalar(
        sa.select(models.offline_order_gateway_leases.c.status).where(
            models.offline_order_gateway_leases.c.branch_id == command["branch_id"],
            models.offline_order_gateway_leases.c.organization_id == command["organization_id"],
            models.offline_order_gateway_leases.c.device_id == command["device_id"],
            models.offline_order_gateway_leases.c.lease_epoch == command["lease_epoch"],
        )
    )
    if released != HANDOFF_STATUS:
        raise BusinessError("offline_handoff_transition_invalid", "Gateway lease changed")
    _audit_release(session, command, digest, released_at)
    if commit:
        session.commit()
    return _receipt(row)


def renew_gateway_catalog(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    lease_epoch: int,
    public_key: str,
    private_key: Any,
    kid: str,
    now: datetime,
    catalog_schema: str | None = None,
) -> dict[str, Any]:
    """Extend the same gateway epoch and issue a fresh signed bundle.

    Expiry prevents ordinary commands but cannot strand an already-authorized
    gateway with open orders.  Only the same registered key/device can renew;
    it never transfers authority to another gateway.
    """
    from restaurant_os.catalog_classification_rollout import _lock

    _lock(session, organization_id)
    issued_at = _utc(now)
    lock_gateway_branch(session, organization_id=organization_id, branch_id=branch_id)
    lease = (
        session.execute(
            sa.select(models.offline_order_gateway_leases)
            .where(
                models.offline_order_gateway_leases.c.branch_id == branch_id,
                models.offline_order_gateway_leases.c.organization_id == organization_id,
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    normalized_key = (
        _public_key(public_key)
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )
    if (
        lease is None
        or lease["status"] != "ACTIVE"
        or lease["device_id"] != device_id
        or lease["lease_epoch"] != lease_epoch
        or lease["public_key"] != normalized_key
    ):
        raise BusinessError("offline_gateway_lease_invalid", "Gateway lease is invalid")
    session.execute(
        models.offline_order_gateway_leases.update()
        .where(models.offline_order_gateway_leases.c.branch_id == branch_id)
        .values(expires_at=issued_at + ORDER_OFFLINE_TTL)
    )
    return bootstrap_order_bundle(
        session,
        organization_id=organization_id,
        branch_id=branch_id,
        device_id=device_id,
        lease_epoch=lease_epoch,
        public_key=public_key,
        private_key=private_key,
        kid=kid,
        now=now,
        commit=True,
        catalog_schema=catalog_schema,
    )


def recover_gateway_lease(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    actor_id: str,
    public_key: str,
    handoff_id: str,
    now: datetime,
    commit: bool = True,
) -> dict[str, Any]:
    """Transfer a released branch authority to a later, monotonic epoch."""
    issued_at = _utc(now)
    try:
        if str(UUID(handoff_id)) != handoff_id:
            raise ValueError("handoff")
    except ValueError as exc:
        raise BusinessError(
            "offline_gateway_recovery_invalid", "Handoff identity is invalid"
        ) from exc
    normalized_key = (
        _public_key(public_key)
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )
    lock_gateway_branch(session, organization_id=organization_id, branch_id=branch_id)
    lease = (
        session.execute(
            sa.select(models.offline_order_gateway_leases)
            .where(
                models.offline_order_gateway_leases.c.branch_id == branch_id,
                models.offline_order_gateway_leases.c.organization_id == organization_id,
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    handoff = (
        session.execute(
            sa.select(models.offline_order_handoffs).where(
                models.offline_order_handoffs.c.handoff_id == handoff_id,
                models.offline_order_handoffs.c.organization_id == organization_id,
                models.offline_order_handoffs.c.branch_id == branch_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        lease is not None
        and handoff is not None
        and lease["status"] == "ACTIVE"
        and lease["device_id"] == device_id
        and lease["public_key"] == normalized_key
        and lease["lease_epoch"] == handoff["lease_epoch"] + 1
    ):
        return {
            "branch_id": branch_id,
            "status": "active",
            "lease_epoch": lease["lease_epoch"],
            "recovered_from_handoff_id": handoff_id,
        }
    if (
        lease is None
        or lease["status"] != HANDOFF_STATUS
        or handoff is None
        or handoff["status"] != HANDOFF_STATUS
        or handoff["lease_epoch"] != lease["lease_epoch"]
    ):
        raise BusinessError(
            "offline_gateway_recovery_required", "Gateway recovery is not authorized"
        )
    next_epoch = int(lease["lease_epoch"]) + 1
    session.execute(
        models.offline_order_gateway_leases.update()
        .where(
            models.offline_order_gateway_leases.c.branch_id == branch_id,
            models.offline_order_gateway_leases.c.lease_epoch == lease["lease_epoch"],
            models.offline_order_gateway_leases.c.status == HANDOFF_STATUS,
        )
        .values(
            device_id=device_id,
            actor_id=actor_id,
            public_key=normalized_key,
            lease_epoch=next_epoch,
            fencing_token=secrets.token_hex(32),
            status="ACTIVE",
            issued_at=issued_at,
            expires_at=issued_at + ORDER_OFFLINE_TTL,
        )
    )
    if commit:
        session.commit()
    return {
        "branch_id": branch_id,
        "status": "active",
        "lease_epoch": next_epoch,
        "recovered_from_handoff_id": handoff_id,
    }


def validate_handoff_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "handoff_id",
        "organization_id",
        "branch_id",
        "device_id",
        "lease_epoch",
        "watermark",
        "commands",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise BusinessError(
            "offline_handoff_manifest_invalid", "Gateway handoff manifest is invalid"
        )
    if manifest["schema_version"] != HANDOFF_SCHEMA:
        raise BusinessError(
            "offline_handoff_manifest_invalid", "Gateway handoff manifest is invalid"
        )
    for field in ("handoff_id", "organization_id", "branch_id", "device_id"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value:
            raise BusinessError(
                "offline_handoff_manifest_invalid", "Gateway handoff manifest is invalid"
            )
    try:
        if str(UUID(str(manifest["handoff_id"]))) != manifest["handoff_id"]:
            raise ValueError("handoff")
    except ValueError as exc:
        raise BusinessError(
            "offline_handoff_manifest_invalid", "Gateway handoff manifest is invalid"
        ) from exc
    if (
        isinstance(manifest["lease_epoch"], bool)
        or not isinstance(manifest["lease_epoch"], int)
        or manifest["lease_epoch"] < 1
        or isinstance(manifest["watermark"], bool)
        or not isinstance(manifest["watermark"], int)
        or manifest["watermark"] < 0
        or not isinstance(manifest["commands"], list)
    ):
        raise BusinessError(
            "offline_handoff_manifest_invalid", "Gateway handoff manifest is invalid"
        )
    entries: list[dict[str, Any]] = []
    expected_local = 1
    for raw in manifest["commands"]:
        if not isinstance(raw, dict) or set(raw) != {
            "local_sequence",
            "command_id",
            "command_hash",
            "aggregate_id",
            "sequence",
        }:
            raise BusinessError(
                "offline_handoff_manifest_invalid", "Gateway handoff command is invalid"
            )
        if (
            any(
                isinstance(raw[field], bool) or not isinstance(raw[field], int) or raw[field] < 1
                for field in ("local_sequence", "sequence")
            )
            or raw["local_sequence"] != expected_local
        ):
            raise BusinessError(
                "offline_handoff_manifest_invalid", "Gateway handoff command is invalid"
            )
        for field in ("command_id", "aggregate_id"):
            try:
                if not isinstance(raw[field], str) or str(UUID(raw[field])) != raw[field]:
                    raise ValueError(field)
            except ValueError as exc:
                raise BusinessError(
                    "offline_handoff_manifest_invalid", "Gateway handoff command is invalid"
                ) from exc
        if (
            not isinstance(raw["command_hash"], str)
            or len(raw["command_hash"]) != 64
            or any(character not in "0123456789abcdef" for character in raw["command_hash"])
        ):
            raise BusinessError(
                "offline_handoff_manifest_invalid", "Gateway handoff command is invalid"
            )
        entries.append(dict(raw))
        expected_local += 1
    if manifest["watermark"] != len(entries):
        raise BusinessError(
            "offline_handoff_manifest_invalid", "Gateway handoff watermark is invalid"
        )
    return {**manifest, "commands": entries}


def _require_complete_epoch(session: Session, manifest: dict[str, Any]) -> None:
    central = [
        dict(row)
        for row in session.execute(
            sa.select(
                models.offline_order_inbox.c.command_id,
                models.offline_order_inbox.c.command_hash,
                models.offline_order_inbox.c.aggregate_id,
                models.offline_order_inbox.c.sequence,
                models.offline_order_inbox.c.status,
                models.offline_order_inbox.c.envelope,
            ).where(
                models.offline_order_inbox.c.organization_id == manifest["organization_id"],
                models.offline_order_inbox.c.branch_id == manifest["branch_id"],
                models.offline_order_inbox.c.device_id == manifest["device_id"],
                models.offline_order_inbox.c.lease_epoch == manifest["lease_epoch"],
            )
        ).mappings()
    ]
    expected = {
        (
            row["command_id"],
            row["command_hash"],
            row["aggregate_id"],
            row["sequence"],
            int((row["envelope"] or {}).get("local_sequence", -1)),
        )
        for row in central
    }
    supplied = {
        (
            row["command_id"],
            row["command_hash"],
            row["aggregate_id"],
            row["sequence"],
            row["local_sequence"],
        )
        for row in manifest["commands"]
    }
    if expected != supplied or any(row["status"] != "CONFIRMED" for row in central):
        raise BusinessError(
            "offline_handoff_reconciliation_incomplete",
            "Gateway commands are not completely confirmed",
        )


def _verify_signature(public_key: str, manifest: dict[str, Any], signature: str) -> None:
    try:
        encoded = signature + "=" * (-len(signature) % 4)
        _public_key(public_key).verify(
            base64.urlsafe_b64decode(encoded), canonical_handoff_manifest(manifest)
        )
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise BusinessError(
            "offline_handoff_signature_invalid", "Gateway handoff signature is invalid"
        ) from exc


def _receipt(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "handoff_id": row["handoff_id"],
        "status": "released",
        "branch_id": row["branch_id"],
        "lease_epoch": row["lease_epoch"],
        "watermark": row["watermark"],
        "manifest_hash": row["manifest_hash"],
    }


def _audit_release(session: Session, manifest: dict[str, Any], digest: str, now: datetime) -> None:
    session.execute(
        models.audit_events.insert().values(
            id=str(
                uuid5(NAMESPACE_URL, f"offline-order-handoff:{manifest['handoff_id']}:{digest}")
            ),
            organization_id=manifest["organization_id"],
            branch_id=manifest["branch_id"],
            actor_user_id=None,
            action="offline_order_gateway.released",
            entity_type="offline_order_gateway_lease",
            entity_id=manifest["branch_id"],
            correlation_id=manifest["handoff_id"],
            payload={
                "lease_epoch": manifest["lease_epoch"],
                "watermark": manifest["watermark"],
                "manifest_hash": digest,
            },
            created_at=now,
        )
    )

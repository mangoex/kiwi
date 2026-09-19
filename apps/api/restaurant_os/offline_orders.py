"""Central retained-bundle/inbox boundary for ORD-OFF001."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.config import get_settings
from restaurant_os.offline_order_contracts import (
    canonical_envelope,
    command_hash,
    intention_hash,
    validate_envelope,
)
from restaurant_os.operations import BusinessError

ORDER_OFFLINE_TTL = timedelta(hours=2)


def lock_gateway_branch(session: Session, *, organization_id: str, branch_id: str) -> None:
    """Serialize lease acquisition and direct order writers on the branch row."""
    branch = session.scalar(
        sa.select(models.branches.c.id)
        .where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == organization_id,
        )
        .with_for_update()
    )
    if branch is None:
        raise BusinessError("offline_gateway_branch_invalid", "Gateway branch is invalid")


def active_catalog_session(session: Session) -> Session:
    return session


def hydrate_bundle(
    engine: Any, bundle: dict[str, Any], include_operational_seed: bool = False
) -> Session:
    """Install a verified retained bundle into a dedicated read-only SQLite catalog."""
    from restaurant_os.offline_order_catalog import hydrate_catalog_snapshot

    if not isinstance(bundle, dict):
        raise BusinessError("offline_bundle_invalid", "Bundle is invalid")
    required = {"manifest", "catalog", "operational_seed"}
    if not required.issubset(bundle):
        raise BusinessError("offline_bundle_invalid", "Bundle is invalid")
    return hydrate_catalog_snapshot(
        engine,
        manifest=bundle["manifest"],
        catalog=bundle["catalog"],
        # Some frozen catalog rows (notably compositions) retain actor foreign
        # keys, so the minimal operational seed is required for a valid SQLite
        # catalog even when callers do not need to inspect it themselves.
        operational_seed=bundle["operational_seed"],
    )


def verify_bundle(bundle: dict[str, Any], keyring: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict) or set(bundle) != {
        "manifest",
        "catalog",
        "operational_seed",
        "hash",
        "signature",
        "kid",
    }:
        raise BusinessError("offline_bundle_invalid", "Bundle is invalid")
    manifest = bundle["manifest"]
    required_manifest = {
        "schema_version",
        "organization_id",
        "branch_id",
        "device_id",
        "bundle_id",
        "bundle_hash",
        "lease_epoch",
        "issued_at",
        "expires_at",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required_manifest
        or manifest.get("schema_version") != "ord-off/v1"
        or not _valid_bundle_manifest(manifest)
    ):
        raise BusinessError("offline_bundle_invalid", "Bundle manifest is invalid")
    canonical = _canonical_bundle_payload(bundle)
    if hashlib.sha256(canonical).hexdigest() != bundle["hash"]:
        raise BusinessError("offline_bundle_hash_invalid", "Bundle hash is invalid")
    _verify(str(bundle["signature"]), canonical, keyring.get(str(bundle["kid"])))
    if manifest.get("bundle_hash") != bundle["hash"]:
        raise BusinessError("offline_bundle_invalid", "Bundle manifest is invalid")
    return dict(bundle)


def verify_order_grant(
    token: str, keyring: dict[str, Any], now: datetime, check_expiry: bool = True
) -> dict[str, Any]:
    try:
        header64, payload64, signature = token.split(".")
        header = _json_object(_decode(header64))
        payload = _json_object(_decode(payload64))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BusinessError("offline_order_grant_invalid", "Order grant is invalid") from exc
    if (
        set(header) != {"alg", "kid", "typ", "version"}
        or header.get("alg") != "EdDSA"
        or header.get("typ") != "order_grant.v3"
        or header.get("version") != 3
        or not isinstance(header.get("kid"), str)
        or not header["kid"]
    ):
        raise BusinessError("offline_order_grant_invalid", "Order grant is invalid")
    _verify(signature, f"{header64}.{payload64}".encode(), keyring.get(header["kid"]))
    required = {
        "actor_id",
        "organization_id",
        "branch_id",
        "device_id",
        "bundle_id",
        "bundle_hash",
        "lease_epoch",
        "capabilities",
        "iat",
        "exp",
        "schema_version",
    }
    if set(payload) != required or not _valid_grant_payload(payload):
        raise BusinessError("offline_order_grant_invalid", "Order grant is invalid")
    if check_expiry and (
        now.tzinfo is None or not payload["iat"] <= int(now.timestamp()) < payload["exp"]
    ):
        raise BusinessError("offline_order_grant_expired", "Order grant expired")
    return payload


COMMAND_CAPABILITIES = {
    "create": "orders.create",
    "pay": "payments.confirm",
    "kds_transition": "kds.tasks.operate",
    "amend": "orders.amend",
    "cancel": "orders.cancel",
    "fulfill": "orders.fulfill",
}
READ_CAPABILITIES = {"pos.operate", "orders.read", "cash.shift.read"}
ALLOWED_GRANT_CAPABILITIES = set(COMMAND_CAPABILITIES.values()) | READ_CAPABILITIES


def require_grant_scope(grant: dict[str, Any], envelope: dict[str, Any]) -> None:
    """Bind a verified grant to one signed envelope before any domain call."""
    bindings = (
        ("actor_id", "actor_id"),
        ("organization_id", "organization_id"),
        ("branch_id", "branch_id"),
        ("device_id", "device_id"),
        ("bundle_id", "bundle_id"),
        ("bundle_hash", "bundle_hash"),
        ("lease_epoch", "lease_epoch"),
    )
    if any(grant[source] != envelope[target] for source, target in bindings):
        raise BusinessError("offline_order_grant_scope_invalid", "Order grant scope is invalid")
    required_capability = COMMAND_CAPABILITIES[envelope["command_type"]]
    if required_capability not in grant["capabilities"]:
        raise BusinessError(
            "offline_order_grant_scope_invalid", "Order grant capability is invalid"
        )


def verify_device_signature(public_key: Any, envelope: dict[str, Any]) -> None:
    """Verify the gateway's Ed25519 signature over the complete canonical intent."""
    signature = envelope.get("device_signature")
    if not isinstance(signature, str) or not signature:
        raise BusinessError("offline_order_signature_invalid", "Signature is invalid")
    _verify(signature, canonical_envelope(envelope), public_key)


def sign_bundle(
    bundle: dict[str, Any], private_key: Ed25519PrivateKey | bytes | str, *, kid: str
) -> dict[str, Any]:
    """Create a retained-bundle signature using the stable, non-recursive payload."""
    if not isinstance(kid, str) or not kid:
        raise ValueError("bundle signing key id is required")
    signed = dict(bundle)
    manifest = dict(signed.get("manifest") or {})
    signed["manifest"] = manifest
    canonical = _canonical_bundle_payload(signed)
    digest = hashlib.sha256(canonical).hexdigest()
    manifest["bundle_hash"] = digest
    signed["hash"] = digest
    signed["kid"] = kid
    signed["signature"] = _b64encode(_private_key(private_key).sign(canonical))
    return signed


def offline_order_signing_material() -> tuple[Ed25519PrivateKey, str]:
    """Load the central Ed25519 issuer key; configuration failure is fail-closed."""
    settings = get_settings()
    if not settings.offline_grant_private_key or not settings.offline_grant_key_id:
        raise BusinessError(
            "offline_order_signing_unavailable", "Offline order signing is unavailable"
        )
    try:
        return _private_key(settings.offline_grant_private_key), settings.offline_grant_key_id
    except (TypeError, ValueError) as exc:
        raise BusinessError(
            "offline_order_signing_unavailable", "Offline order signing is unavailable"
        ) from exc


def retain_bundle(
    session: Session,
    bundle: dict[str, Any],
    keyring: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Persist only the exact signed bundle that reconciliation will later hydrate."""
    verified = verify_bundle(bundle, keyring)
    issued_at = _utc(now)
    manifest = verified["manifest"]
    if not manifest["issued_at"] <= int(issued_at.timestamp()) < manifest["expires_at"]:
        raise BusinessError("offline_order_bundle_expired", "Bundle is expired")
    existing = (
        session.execute(
            sa.select(models.offline_order_bundles).where(
                models.offline_order_bundles.c.id == manifest["bundle_id"]
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        if existing["bundle_hash"] != verified["hash"]:
            raise BusinessError("offline_order_bundle_conflict", "Bundle identity differs")
        return dict(existing)
    row = {
        "id": manifest["bundle_id"],
        "organization_id": manifest["organization_id"],
        "branch_id": manifest["branch_id"],
        "device_id": manifest["device_id"],
        "bundle_hash": verified["hash"],
        "manifest": manifest,
        "catalog": verified["catalog"],
        "operational_seed": verified["operational_seed"],
        "kid": verified["kid"],
        "signature": verified["signature"],
        "issued_at": datetime.fromtimestamp(manifest["issued_at"], UTC),
        "expires_at": datetime.fromtimestamp(manifest["expires_at"], UTC),
    }
    session.execute(models.offline_order_bundles.insert().values(**row))
    return row


def acquire_gateway_lease(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    actor_id: str,
    public_key: Ed25519PublicKey | bytes | str,
    now: datetime,
) -> dict[str, Any]:
    """Acquire or renew the sole explicit gateway lease for one branch."""
    issued_at = _utc(now)
    lock_gateway_branch(session, organization_id=organization_id, branch_id=branch_id)
    normalized_key = (
        _public_key(public_key)
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )
    existing = (
        session.execute(
            sa.select(models.offline_order_gateway_leases)
            .where(models.offline_order_gateway_leases.c.branch_id == branch_id)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    expires_at = issued_at + ORDER_OFFLINE_TTL
    if existing is None:
        lease = {
            "branch_id": branch_id,
            "organization_id": organization_id,
            "device_id": device_id,
            "actor_id": actor_id,
            "public_key": normalized_key,
            "lease_epoch": 1,
            "fencing_token": secrets.token_hex(32),
            "status": "ACTIVE",
            "issued_at": issued_at,
            "expires_at": expires_at,
        }
        session.execute(models.offline_order_gateway_leases.insert().values(**lease))
        return lease
    if (
        existing["organization_id"] != organization_id
        or existing["device_id"] != device_id
        or existing["actor_id"] != actor_id
    ):
        raise BusinessError("offline_gateway_lease_held", "Branch lease belongs to another gateway")
    if existing["status"] != "ACTIVE" or _stored_utc(existing["expires_at"]) <= issued_at:
        raise BusinessError(
            "offline_gateway_lease_recovery_required",
            "Expired or released lease requires explicit recovery",
        )
    if existing["public_key"] != normalized_key:
        raise BusinessError(
            "offline_gateway_key_immutable", "Gateway key is immutable for its lease"
        )
    session.execute(
        models.offline_order_gateway_leases.update()
        .where(
            models.offline_order_gateway_leases.c.branch_id == branch_id,
            models.offline_order_gateway_leases.c.lease_epoch == existing["lease_epoch"],
        )
        .values(expires_at=expires_at)
    )
    return {**dict(existing), "expires_at": expires_at}


def issue_order_grant(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    source_device_id: str,
    actor_id: str,
    bundle_id: str,
    lease_epoch: int,
    capabilities: list[str],
    private_key: Ed25519PrivateKey | bytes | str,
    kid: str,
    now: datetime,
) -> dict[str, Any]:
    """Issue and retain a two-hour signed grant after checking lease and bundle identity."""
    issued_at = _utc(now)
    lease = _require_active_lease(
        session,
        organization_id=organization_id,
        branch_id=branch_id,
        device_id=source_device_id,
        lease_epoch=lease_epoch,
        now=issued_at,
    )
    bundle = (
        session.execute(
            sa.select(models.offline_order_bundles).where(
                models.offline_order_bundles.c.id == bundle_id,
                models.offline_order_bundles.c.organization_id == organization_id,
                models.offline_order_bundles.c.branch_id == branch_id,
                models.offline_order_bundles.c.device_id == source_device_id,
            )
        )
        .mappings()
        .first()
    )
    if bundle is None or _stored_utc(bundle["expires_at"]) <= issued_at:
        raise BusinessError("offline_order_bundle_unavailable", "Retained bundle is unavailable")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(capability not in ALLOWED_GRANT_CAPABILITIES for capability in capabilities)
    ):
        raise BusinessError("offline_order_grant_invalid", "Order grant capabilities are invalid")
    expires_at = min(
        issued_at + ORDER_OFFLINE_TTL,
        _stored_utc(bundle["expires_at"]),
        _stored_utc(lease["expires_at"]),
    )
    claims = {
        "schema_version": "ord-off-grant/v3",
        "organization_id": organization_id,
        "branch_id": branch_id,
        "device_id": source_device_id,
        "actor_id": actor_id,
        "bundle_id": bundle_id,
        "bundle_hash": bundle["bundle_hash"],
        "lease_epoch": lease_epoch,
        "capabilities": sorted(set(capabilities)),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = _sign_grant(claims, private_key, kid=kid)
    session.execute(
        models.offline_order_grants.insert().values(
            id=str(uuid4()),
            organization_id=organization_id,
            branch_id=branch_id,
            device_id=source_device_id,
            actor_id=actor_id,
            bundle_id=bundle_id,
            bundle_hash=bundle["bundle_hash"],
            lease_epoch=lease_epoch,
            capabilities=claims["capabilities"],
            token=token,
            issued_at=issued_at,
            expires_at=expires_at,
        )
    )
    return {"grant": token, "expires_at": expires_at}


def bootstrap_order_bundle(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    lease_epoch: int,
    public_key: Ed25519PublicKey | bytes | str,
    private_key: Ed25519PrivateKey | bytes | str,
    kid: str,
    now: datetime,
    commit: bool = True,
) -> dict[str, Any]:
    """Issue the signed, retained branch bundle for the active gateway only."""
    from restaurant_os.offline_order_catalog import (
        build_catalog_snapshot,
        build_operational_seed,
    )

    issued_at = _utc(now)
    lease = _require_active_lease(
        session,
        organization_id=organization_id,
        branch_id=branch_id,
        device_id=device_id,
        lease_epoch=lease_epoch,
        now=issued_at,
    )
    normalized_public_key = (
        _public_key(public_key)
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )
    if lease["public_key"] != normalized_public_key:
        raise BusinessError("offline_gateway_key_immutable", "Gateway key does not match lease")
    actor_ids = [
        row["id"]
        for row in session.execute(
            sa.select(models.users.c.id)
            .select_from(
                models.users.join(
                    models.user_roles, models.user_roles.c.user_id == models.users.c.id
                )
            )
            .join(models.roles, models.roles.c.id == models.user_roles.c.role_id)
            .where(
                models.users.c.organization_id == organization_id,
                models.users.c.status == "active",
                models.roles.c.organization_id == organization_id,
                sa.or_(
                    models.roles.c.scope == "organization",
                    sa.and_(
                        models.roles.c.scope == "branch",
                        models.user_roles.c.branch_id == branch_id,
                    ),
                ),
            )
            .distinct()
        ).mappings()
    ]
    if not actor_ids:
        raise BusinessError("offline_bundle_seed_invalid", "Branch has no active authorized actors")
    issued = int(issued_at.timestamp())
    bundle = sign_bundle(
        {
            "manifest": {
                "schema_version": "ord-off/v1",
                "organization_id": organization_id,
                "branch_id": branch_id,
                "device_id": device_id,
                "bundle_id": str(uuid4()),
                "bundle_hash": "",
                "lease_epoch": lease_epoch,
                "issued_at": issued,
                "expires_at": int((issued_at + ORDER_OFFLINE_TTL).timestamp()),
            },
            "catalog": build_catalog_snapshot(
                session, organization_id=organization_id, branch_id=branch_id
            ),
            "operational_seed": build_operational_seed(
                session,
                organization_id=organization_id,
                branch_id=branch_id,
                actor_ids=actor_ids,
            ),
        },
        private_key,
        kid=kid,
    )
    retain_bundle(session, bundle, {kid: _private_key(private_key).public_key()}, now=issued_at)
    if commit:
        session.commit()
    return bundle


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _verify(signature: str, signed: bytes, key: Any) -> None:
    try:
        public = (
            key
            if isinstance(key, Ed25519PublicKey)
            else serialization.load_pem_public_key(key.encode() if isinstance(key, str) else key)
        )
        if not isinstance(public, Ed25519PublicKey):
            raise ValueError("key type")
        public.verify(_decode(signature), signed)
    except (ValueError, TypeError, InvalidSignature, AttributeError) as exc:
        raise BusinessError("offline_order_signature_invalid", "Signature is invalid") from exc


def _private_key(value: Ed25519PrivateKey | bytes | str) -> Ed25519PrivateKey:
    if isinstance(value, Ed25519PrivateKey):
        return value
    encoded = value.encode("utf-8") if isinstance(value, str) else value
    key = serialization.load_pem_private_key(encoded, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("offline order signing key must be Ed25519")
    return key


def _public_key(value: Ed25519PublicKey | bytes | str) -> Ed25519PublicKey:
    if isinstance(value, Ed25519PublicKey):
        return value
    encoded = value.encode("utf-8") if isinstance(value, str) else value
    key = serialization.load_pem_public_key(encoded)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("offline gateway key must be Ed25519")
    return key


def _sign_grant(
    claims: dict[str, Any], private_key: Ed25519PrivateKey | bytes | str, *, kid: str
) -> str:
    if not isinstance(kid, str) or not kid:
        raise ValueError("grant signing key id is required")
    header = {"alg": "EdDSA", "kid": kid, "typ": "order_grant.v3", "version": 3}
    encoded_header = _b64encode(_canonical_json(header))
    encoded_claims = _b64encode(_canonical_json(claims))
    signed = f"{encoded_header}.{encoded_claims}".encode("ascii")
    return f"{signed.decode('ascii')}.{_b64encode(_private_key(private_key).sign(signed))}"


def _require_active_lease(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    lease_epoch: int,
    now: datetime,
) -> dict[str, Any]:
    lock_gateway_branch(session, organization_id=organization_id, branch_id=branch_id)
    lease = (
        session.execute(
            sa.select(models.offline_order_gateway_leases).where(
                models.offline_order_gateway_leases.c.branch_id == branch_id
            )
        )
        .mappings()
        .first()
    )
    expires_at = _stored_utc(lease["expires_at"]) if lease is not None else None
    if (
        lease is None
        or lease["organization_id"] != organization_id
        or lease["device_id"] != device_id
        or lease["lease_epoch"] != lease_epoch
        or lease["status"] != "ACTIVE"
        or not isinstance(expires_at, datetime)
        or expires_at <= _utc(now)
    ):
        raise BusinessError("offline_gateway_lease_invalid", "Gateway lease is invalid")
    return dict(lease)


def _retained_bundle(session: Session, command: dict[str, Any]) -> dict[str, Any]:
    retained = (
        session.execute(
            sa.select(models.offline_order_bundles).where(
                models.offline_order_bundles.c.id == command["bundle_id"],
                models.offline_order_bundles.c.bundle_hash == command["bundle_hash"],
                models.offline_order_bundles.c.organization_id == command["organization_id"],
                models.offline_order_bundles.c.branch_id == command["branch_id"],
                models.offline_order_bundles.c.device_id == command["device_id"],
            )
        )
        .mappings()
        .first()
    )
    if retained is None:
        raise BusinessError("offline_order_bundle_unavailable", "Retained bundle is unavailable")
    return {
        "manifest": retained["manifest"],
        "catalog": retained["catalog"],
        "operational_seed": retained["operational_seed"],
        "hash": retained["bundle_hash"],
        "signature": retained["signature"],
        "kid": retained["kid"],
    }


def _lock_reconciliation(session: Session, command: dict[str, Any]) -> None:
    """Serialize both an aggregate sequence and a command replay on PostgreSQL."""
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        for value in (command["aggregate_id"], command["command_id"]):
            session.execute(
                sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
                {"value": value},
            )


def _next_checkpoint(session: Session) -> int:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(sa.text("SELECT pg_advisory_xact_lock(461287)"))
    current = session.scalar(sa.select(sa.func.max(models.offline_order_inbox.c.checkpoint)))
    return int(current or 0) + 1


def _require_predecessor(session: Session, command: dict[str, Any]) -> None:
    sequence = command["sequence"]
    predecessor = command["previous_hash"]
    if sequence == 1:
        if predecessor is not None:
            raise BusinessError(
                "offline_order_predecessor_invalid", "First command has a predecessor"
            )
        return
    if predecessor is None:
        raise BusinessError("offline_order_predecessor_invalid", "Command predecessor is required")
    prior = (
        session.execute(
            sa.select(
                models.offline_order_inbox.c.command_hash,
                models.offline_order_inbox.c.status,
            ).where(
                models.offline_order_inbox.c.aggregate_id == command["aggregate_id"],
                models.offline_order_inbox.c.sequence == sequence - 1,
            )
        )
        .mappings()
        .first()
    )
    if prior is None:
        raise BusinessError(
            "offline_order_predecessor_pending", "Command predecessor is not confirmed"
        )
    if prior["command_hash"] != predecessor:
        raise BusinessError(
            "offline_order_predecessor_invalid", "Command predecessor does not match"
        )
    if prior["status"] != "CONFIRMED":
        raise BusinessError(
            "offline_order_predecessor_conflict", "Command predecessor did not confirm"
        )


def retained_bundle_for_command(session: Session, envelope: dict[str, Any]) -> dict[str, Any]:
    """Public loader for a dedicated reconciliation catalog session."""
    command = validate_envelope(envelope)
    return _retained_bundle(session, command)


def _require_bundle_scope(
    manifest: dict[str, Any], command: dict[str, Any], accepted_at: datetime
) -> None:
    bindings = (
        ("organization_id", "organization_id"),
        ("branch_id", "branch_id"),
        ("device_id", "device_id"),
        ("bundle_id", "bundle_id"),
        ("bundle_hash", "bundle_hash"),
        ("lease_epoch", "lease_epoch"),
    )
    if any(manifest[source] != command[target] for source, target in bindings):
        raise BusinessError("offline_order_bundle_scope_invalid", "Bundle scope is invalid")
    timestamp = int(accepted_at.timestamp())
    if not manifest["issued_at"] <= timestamp < manifest["expires_at"]:
        raise BusinessError("offline_order_bundle_expired", "Bundle is expired")


def _parse_accepted_at(value: Any) -> datetime:
    try:
        accepted_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusinessError(
            "offline_order_envelope_invalid", "Offline order timestamp is invalid"
        ) from exc
    return _utc(accepted_at)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("offline order timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _stored_utc(value: Any) -> datetime:
    """Normalize database timestamps; SQLite returns UTC columns without tzinfo."""
    if not isinstance(value, datetime):
        raise ValueError("offline order stored timestamp is invalid")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _canonical_bundle_payload(bundle: dict[str, Any]) -> bytes:
    manifest = dict(bundle["manifest"])
    manifest.pop("bundle_hash", None)
    return json.dumps(
        {
            "manifest": manifest,
            "catalog": bundle["catalog"],
            "operational_seed": bundle["operational_seed"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _json_object(value: bytes) -> dict[str, Any]:
    decoded = json.loads(value.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("expected JSON object")
    return decoded


def _valid_grant_payload(payload: dict[str, Any]) -> bool:
    if any(
        not isinstance(payload[field], str) or not payload[field]
        for field in (
            "actor_id",
            "organization_id",
            "branch_id",
            "device_id",
            "bundle_id",
            "bundle_hash",
        )
    ):
        return False
    if len(payload["bundle_hash"]) != 64 or any(
        character not in "0123456789abcdef" for character in payload["bundle_hash"]
    ):
        return False
    if any(
        isinstance(payload[field], bool) or not isinstance(payload[field], int)
        for field in ("iat", "exp", "lease_epoch")
    ):
        return False
    if (
        payload.get("schema_version") != "ord-off-grant/v3"
        or payload["lease_epoch"] < 1
        or not (payload["iat"] < payload["exp"] <= payload["iat"] + 7200)
    ):
        return False
    return (
        isinstance(payload["capabilities"], list)
        and bool(payload["capabilities"])
        and all(isinstance(capability, str) for capability in payload["capabilities"])
        and len(payload["capabilities"]) == len(set(payload["capabilities"]))
        and all(capability in ALLOWED_GRANT_CAPABILITIES for capability in payload["capabilities"])
    )


def _valid_bundle_manifest(manifest: dict[str, Any]) -> bool:
    if any(
        not isinstance(manifest[field], str) or not manifest[field]
        for field in ("organization_id", "branch_id", "device_id", "bundle_id", "bundle_hash")
    ):
        return False
    if len(manifest["bundle_hash"]) != 64 or any(
        character not in "0123456789abcdef" for character in manifest["bundle_hash"]
    ):
        return False
    if any(
        isinstance(manifest[field], bool) or not isinstance(manifest[field], int)
        for field in ("lease_epoch", "issued_at", "expires_at")
    ):
        return False
    return bool(
        manifest["lease_epoch"] >= 1
        and manifest["issued_at"] < manifest["expires_at"] <= manifest["issued_at"] + 7200
    )


def execute_order_intent(
    session: Session,
    envelope: dict[str, Any],
    catalog_session: Session,
    *,
    commit: bool = False,
) -> dict[str, Any]:
    """Execute exactly one canonical order operation without inbox or transport work.

    The caller is responsible for grant, lease, bundle and signature validation.
    This function deliberately never commits its own unit of work by default.
    """
    from restaurant_os import operations
    from restaurant_os.order_execution import ExecutionContext, next_id, order_execution_context

    command = validate_envelope(envelope)
    accepted_at = datetime.fromisoformat(command["accepted_at"].replace("Z", "+00:00"))
    context = ExecutionContext(
        command_id=command["command_id"],
        accepted_at=accepted_at,
        folio=_offline_folio(command),
        catalog_session=catalog_session,
        gateway_epoch=command["lease_epoch"],
        execution_mode="offline_reconcile",
    )
    _validate_aggregate_target(session, command, context, next_id)
    with order_execution_context(context):
        result = _execute_canonical_operation(session, command, operations)
    if command["command_type"] == "create" and result.get("id") != command["aggregate_id"]:
        raise BusinessError(
            "offline_order_aggregate_mismatch", "Offline order aggregate identity differs"
        )
    if commit:
        session.commit()
    return _domain_result(_json_safe_result(result))


def reconcile_order_command(
    session: Session,
    envelope: dict[str, Any],
    catalog_session: Session | None = None,
    *,
    keyring: dict[str, Any],
    now: datetime,
    commit: bool = False,
) -> dict[str, Any]:
    """Validate a retained offline command and atomically execute/domain-inbox it."""
    del catalog_session
    command = validate_envelope(envelope)
    digest = command_hash(command)
    intent = intention_hash(command)
    _lock_reconciliation(session, command)
    existing = (
        session.execute(
            sa.select(models.offline_order_inbox).where(
                models.offline_order_inbox.c.command_id == command["command_id"]
            )
        )
        .mappings()
        .first()
    )
    accepted_at = _parse_accepted_at(command["accepted_at"])
    if accepted_at > _utc(now):
        raise BusinessError(
            "offline_order_accepted_at_future", "Offline order timestamp is in the future"
        )
    grant = verify_order_grant(command["grant"], keyring, accepted_at)
    require_grant_scope(grant, command)
    lease = _require_active_lease(
        session,
        organization_id=command["organization_id"],
        branch_id=command["branch_id"],
        device_id=command["device_id"],
        lease_epoch=command["lease_epoch"],
        now=accepted_at,
    )
    verify_device_signature(lease["public_key"], command)
    from restaurant_os.operations import AuthorizationError, require_permission
    from restaurant_os.order_execution import (
        ExecutionContext,
        defer_authorization_audit,
        order_execution_context,
    )

    context = ExecutionContext(
        command_id=command["command_id"],
        accepted_at=accepted_at,
        folio=_offline_folio(command),
        gateway_epoch=command["lease_epoch"],
        execution_mode="offline_reconcile",
    )
    if existing is not None:
        with defer_authorization_audit() as denials:
            try:
                with order_execution_context(context):
                    require_permission(
                        session,
                        command["actor_id"],
                        COMMAND_CAPABILITIES[command["command_type"]],
                        command["branch_id"],
                    )
            except AuthorizationError:
                _persist_deferred_authorization_denials(session, command, denials, now)
                if commit:
                    session.commit()
                raise
        if existing["command_hash"] != digest or existing["intention_hash"] != intent:
            raise BusinessError("offline_order_idempotency_conflict", "Command intention differs")
        return _domain_result(existing["result"])
    bundle = _retained_bundle(session, command)
    verify_bundle(bundle, keyring)
    _require_bundle_scope(bundle["manifest"], command, accepted_at)
    receipt: dict[str, Any]
    try:
        _require_predecessor(session, command)
    except BusinessError as exc:
        if exc.code == "offline_order_predecessor_pending":
            raise
        receipt = _reconciliation_receipt(command, _next_checkpoint(session), exc.code)
        _insert_reconciliation_receipt(
            session,
            command,
            digest,
            intent,
            receipt,
            "CONFLICT",
            now,
        )
        if commit:
            session.commit()
        return receipt
    catalog_engine = sa.create_engine("sqlite://")
    retained_catalog = hydrate_bundle(catalog_engine, bundle, include_operational_seed=True)
    try:
        with defer_authorization_audit() as denials:
            try:
                with session.begin_nested():
                    with order_execution_context(context):
                        require_permission(
                            session,
                            command["actor_id"],
                            COMMAND_CAPABILITIES[command["command_type"]],
                            command["branch_id"],
                        )
                    execute_order_intent(session, command, retained_catalog, commit=False)
                    receipt = _reconciliation_receipt(
                        command, _next_checkpoint(session), "confirmed"
                    )
                    _insert_reconciliation_receipt(
                        session,
                        command,
                        digest,
                        intent,
                        receipt,
                        "CONFIRMED",
                        now,
                    )
            except BusinessError as exc:
                receipt = _reconciliation_receipt(command, _next_checkpoint(session), exc.code)
                _persist_deferred_authorization_denials(session, command, denials, now)
                _insert_reconciliation_receipt(
                    session,
                    command,
                    digest,
                    intent,
                    receipt,
                    "CONFLICT",
                    now,
                )
    finally:
        retained_catalog.close()
        catalog_engine.dispose()
    if commit:
        session.commit()
    return receipt


def _reconciliation_receipt(command: dict[str, Any], checkpoint: int, code: str) -> dict[str, Any]:
    return {
        "command_id": command["command_id"],
        "status": "confirmed" if code == "confirmed" else "conflict",
        "checkpoint": checkpoint,
        "code": code,
    }


def _insert_reconciliation_receipt(
    session: Session,
    command: dict[str, Any],
    digest: str,
    intent: str,
    receipt: dict[str, Any],
    status: str,
    now: datetime,
) -> None:
    session.execute(
        models.offline_order_inbox.insert().values(
            command_id=command["command_id"],
            organization_id=command["organization_id"],
            branch_id=command["branch_id"],
            device_id=command["device_id"],
            actor_id=command["actor_id"],
            bundle_id=command["bundle_id"],
            lease_epoch=command["lease_epoch"],
            checkpoint=receipt["checkpoint"],
            aggregate_id=command["aggregate_id"],
            sequence=command["sequence"],
            command_hash=digest,
            intention_hash=intent,
            envelope=command,
            result=receipt,
            status=status,
            created_at=_utc(now),
        )
    )


def _persist_deferred_authorization_denials(
    session: Session,
    command: dict[str, Any],
    denials: list[dict[str, Any]],
    now: datetime,
) -> None:
    for denial in denials:
        session.execute(
            models.audit_events.insert().values(
                id=str(uuid4()),
                organization_id=command["organization_id"],
                branch_id=denial["branch_id"],
                actor_user_id=denial["actor_user_id"],
                action="authorization.denied",
                entity_type="permission",
                entity_id=denial["permission_code"],
                payload={
                    "permission": denial["permission_code"],
                    "reason": denial["reason"],
                },
                correlation_id=command["command_id"],
                created_at=_utc(now),
            )
        )


def dispatch_order_command(
    session: Session,
    envelope: dict[str, Any],
    catalog_session: Session | None = None,
    *,
    keyring: dict[str, Any],
    now: datetime,
    commit: bool = False,
) -> dict[str, Any]:
    """Compatibility name for the fully guarded central reconciliation boundary."""
    return reconcile_order_command(
        session, envelope, catalog_session, keyring=keyring, now=now, commit=commit
    )


def _execute_canonical_operation(
    session: Session, command: dict[str, Any], operations: Any
) -> dict[str, Any]:
    payload = command["payload"]
    command_type = command["command_type"]
    if command_type == "create":
        _require_payload_fields(
            payload,
            {
                "lines",
                "owner_name",
                "order_type",
                "register_id",
                "customer_id",
                "delivery_address_id",
                "payment_method_intent",
                "driver_id",
                "adjustment_authorization_id",
            },
            {"lines"},
        )
        return _domain_result(
            operations.create_local_order(
                session,
                payload["lines"],
                owner_name=payload.get("owner_name"),
                order_type=payload.get("order_type", "dine-in"),
                branch_id=command["branch_id"],
                register_id=payload.get("register_id"),
                actor_user_id=command["actor_id"],
                customer_id=payload.get("customer_id"),
                delivery_address_id=payload.get("delivery_address_id"),
                payment_method_intent=payload.get("payment_method_intent"),
                driver_id=payload.get("driver_id"),
                adjustment_authorization_id=payload.get("adjustment_authorization_id"),
                idempotency_key=command["idempotency_key"],
                commit=False,
            )
        )
    if command_type == "amend":
        _require_payload_fields(
            payload, {"lines", "expected_version"}, {"lines", "expected_version"}
        )
        return _domain_result(
            operations.amend_order(
                session,
                command["aggregate_id"],
                payload["lines"],
                payload["expected_version"],
                command["idempotency_key"],
                actor_user_id=command["actor_id"],
                commit=False,
            )
        )
    if command_type == "cancel":
        _require_payload_fields(payload, {"reason", "classification"}, set())
        return _domain_result(
            operations.cancel_order(
                session,
                command["aggregate_id"],
                reason=payload.get("reason", "Cancelacion solicitada en POS"),
                classification=payload.get("classification"),
                actor_user_id=command["actor_id"],
                commit=False,
            )
        )
    if command_type == "pay":
        _require_payload_fields(
            payload, {"amount_cents", "method", "register_id"}, {"amount_cents", "register_id"}
        )
        return _domain_result(
            operations.pay_order(
                session,
                command["aggregate_id"],
                payload["amount_cents"],
                method=payload.get("method", "cash"),
                actor_user_id=command["actor_id"],
                register_id=payload.get("register_id"),
                idempotency_key=command["idempotency_key"],
                commit=False,
            )
        )
    if command_type == "kds_transition":
        _require_payload_fields(payload, {"task_id", "status"}, {"task_id", "status"})
        operations.require_permission(
            session, command["actor_id"], "kds.tasks.operate", command["branch_id"]
        )
        return _domain_result(
            operations.advance_kds_task(
                session,
                payload["task_id"],
                payload["status"],
                command["branch_id"],
                actor_user_id=command["actor_id"],
                commit=False,
            )
        )
    if command_type == "fulfill":
        _require_payload_fields(payload, {"command"}, {"command"})
        return _domain_result(
            operations.fulfill_order(
                session,
                command["aggregate_id"],
                payload["command"],
                command["idempotency_key"],
                command["actor_id"],
                commit=False,
            )
        )
    raise BusinessError("offline_order_envelope_invalid", "Offline order command is invalid")


def _require_payload_fields(payload: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if not required.issubset(payload) or not set(payload).issubset(allowed):
        raise BusinessError("offline_order_payload_invalid", "Offline order payload is invalid")


def _domain_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise BusinessError("offline_order_result_invalid", "Offline order result is invalid")
    return {key: item for key, item in value.items()}


def _validate_aggregate_target(
    session: Session, command: dict[str, Any], context: Any, next_id: Any
) -> None:
    if command["command_type"] == "create":
        from restaurant_os.order_execution import order_execution_context

        with order_execution_context(context):
            expected_order_id = next_id()
        if expected_order_id == command["aggregate_id"]:
            return
        raise BusinessError(
            "offline_order_aggregate_mismatch", "Offline order aggregate identity differs"
        )
    if command["command_type"] == "kds_transition":
        task_id = command["payload"].get("task_id")
        task = (
            session.execute(
                sa.select(models.production_tasks.c.order_id).where(
                    models.production_tasks.c.id == task_id,
                    models.production_tasks.c.branch_id == command["branch_id"],
                )
            )
            .mappings()
            .first()
        )
        if task is not None and task["order_id"] == command["aggregate_id"]:
            return
    else:
        order = (
            session.execute(
                sa.select(models.orders.c.id).where(
                    models.orders.c.id == command["aggregate_id"],
                    models.orders.c.branch_id == command["branch_id"],
                    models.orders.c.organization_id == command["organization_id"],
                )
            )
            .mappings()
            .first()
        )
        if order is not None:
            return
    raise BusinessError("offline_order_aggregate_mismatch", "Offline order aggregate is invalid")


def _json_safe_result(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe_result(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_result(item) for item in value]
    if isinstance(value, datetime):
        # SQLite returns persisted UTC columns without tzinfo.  This is a
        # result serializer only; command inputs remain strict in _utc.
        return (
            (value if value.tzinfo is not None else value.replace(tzinfo=UTC))
            .astimezone(UTC)
            .isoformat()
        )
    if isinstance(value, Decimal):
        return str(value)
    return value


def _offline_folio(command: dict[str, Any]) -> str:
    register_id = str(command["payload"].get("register_id", "POS"))
    branch = str(command["branch_id"]).replace("-", "")[:6]
    register = register_id.replace("-", "")[:6]
    identifier = str(command["command_id"]).replace("-", "")
    return f"{branch}-{register}-{identifier}-{int(command['local_sequence']):012d}"

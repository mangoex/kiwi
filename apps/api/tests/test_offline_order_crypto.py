from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os.offline_order_contracts import canonical_envelope
from restaurant_os.offline_orders import (
    require_grant_scope,
    verify_bundle,
    verify_device_signature,
    verify_order_grant,
)
from restaurant_os.operations import BusinessError


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def _bundle(private: Ed25519PrivateKey) -> dict[str, object]:
    manifest = {
        "schema_version": "ord-off/v1",
        "organization_id": "org",
        "branch_id": "branch",
        "device_id": "device",
        "bundle_id": str(uuid4()),
        "bundle_hash": "",
        "lease_epoch": 1,
        "issued_at": 100,
        "expires_at": 7300,
    }
    bundle: dict[str, object] = {
        "manifest": manifest,
        "catalog": {"products": []},
        "operational_seed": {"actors": []},
        "hash": "",
        "signature": "",
        "kid": "central-1",
    }
    signed = _canonical(
        {
            "manifest": {key: value for key, value in manifest.items() if key != "bundle_hash"},
            "catalog": bundle["catalog"],
            "operational_seed": bundle["operational_seed"],
        }
    )
    digest = hashlib.sha256(signed).hexdigest()
    manifest["bundle_hash"] = digest
    bundle["hash"] = digest
    bundle["signature"] = _b64(private.sign(signed))
    return bundle


def _grant(private: Ed25519PrivateKey, exp: int = 200) -> tuple[str, dict[str, object]]:
    header = {"alg": "EdDSA", "typ": "order_grant.v3", "version": 3, "kid": "central-1"}
    claims: dict[str, object] = {
        "schema_version": "ord-off-grant/v3",
        "actor_id": "actor",
        "organization_id": "org",
        "branch_id": "branch",
        "device_id": "device",
        "bundle_id": str(uuid4()),
        "bundle_hash": "a" * 64,
        "lease_epoch": 1,
        "capabilities": ["orders.create"],
        "iat": 100,
        "exp": exp,
    }
    header64, claims64 = _b64(_canonical(header)), _b64(_canonical(claims))
    signed = f"{header64}.{claims64}".encode("ascii")
    return f"{signed.decode('ascii')}.{_b64(private.sign(signed))}", claims


def _envelope(token: str, claims: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "ord-off/v1",
        "command_id": str(uuid4()),
        "command_type": "create",
        "idempotency_key": "command-1",
        "aggregate_id": str(uuid4()),
        "sequence": 1,
        "previous_hash": None,
        "organization_id": claims["organization_id"],
        "branch_id": claims["branch_id"],
        "device_id": claims["device_id"],
        "actor_id": claims["actor_id"],
        "accepted_at": "2026-09-19T00:00:00+00:00",
        "grant": token,
        "bundle_id": claims["bundle_id"],
        "bundle_hash": claims["bundle_hash"],
        "lease_epoch": claims["lease_epoch"],
        "local_sequence": 1,
        "payload": {"lines": []},
        "device_signature": "",
    }


def test_bundle_grant_and_device_signatures_are_ed25519_verified() -> None:
    private = Ed25519PrivateKey.generate()
    bundle = _bundle(private)
    assert verify_bundle(bundle, {"central-1": _public(private)}) == bundle
    token, claims = _grant(private)
    grant = verify_order_grant(
        token, {"central-1": private.public_key()}, datetime.fromtimestamp(150, UTC)
    )
    envelope = _envelope(token, claims)
    envelope["device_signature"] = _b64(private.sign(canonical_envelope(envelope)))
    verify_device_signature(_public(private), envelope)
    require_grant_scope(grant, envelope)


def test_tampering_scope_and_expiry_fail_closed() -> None:
    private = Ed25519PrivateKey.generate()
    bundle = _bundle(private)
    bundle["catalog"] = {"products": ["tampered"]}
    with pytest.raises(BusinessError, match="hash"):
        verify_bundle(bundle, {"central-1": _public(private)})
    token, claims = _grant(private, exp=200)
    with pytest.raises(BusinessError, match="expired"):
        verify_order_grant(token, {"central-1": _public(private)}, datetime.fromtimestamp(200, UTC))
    grant = verify_order_grant(
        token, {"central-1": _public(private)}, datetime.fromtimestamp(150, UTC)
    )
    envelope = _envelope(token, claims)
    envelope["branch_id"] = "other-branch"
    with pytest.raises(BusinessError, match="scope"):
        require_grant_scope(grant, envelope)
    envelope["branch_id"] = claims["branch_id"]
    envelope["device_signature"] = _b64(private.sign(canonical_envelope(envelope)))
    envelope["payload"] = {"lines": ["tampered-after-signing"]}
    with pytest.raises(BusinessError, match="Signature"):
        verify_device_signature(_public(private), envelope)


def test_grant_capabilities_nested_values_fail_closed() -> None:
    private = Ed25519PrivateKey.generate()
    _, claims = _grant(private)
    claims["capabilities"] = [["orders.create"]]
    header = {"alg": "EdDSA", "typ": "order_grant.v3", "version": 3, "kid": "central-1"}
    header64, payload64 = _b64(_canonical(header)), _b64(_canonical(claims))
    signed = f"{header64}.{payload64}".encode("ascii")
    token = f"{signed.decode('ascii')}.{_b64(private.sign(signed))}"
    with pytest.raises(BusinessError, match="grant"):
        verify_order_grant(token, {"central-1": _public(private)}, datetime.fromtimestamp(150, UTC))

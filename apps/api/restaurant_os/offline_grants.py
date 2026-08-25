"""Portable Ed25519 grants for the PCO-008 offline gateway boundary."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

OFFLINE_GRANT_KIND = "offline_grant.v2"
OFFLINE_GRANT_ALGORITHM = "EdDSA"
OFFLINE_GRANT_VERSION = 2
OFFLINE_GRANT_TTL_SECONDS = 60 * 60 * 2
OFFLINE_GRANT_CAPABILITY = "cash.movement.create.v1"


def create_offline_grant_v2(
    payload: Mapping[str, Any],
    private_key: Ed25519PrivateKey | bytes | str,
    *,
    kid: str,
    now: int | None = None,
) -> str:
    if not isinstance(kid, str) or not kid:
        raise ValueError("offline grant kid is required")
    key = _private_key(private_key)
    issued_at = int(time.time()) if now is None else now
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise ValueError("offline grant issue time is invalid")
    body = _grant_payload(payload, issued_at)
    header = {
        "alg": OFFLINE_GRANT_ALGORITHM,
        "kid": kid,
        "typ": OFFLINE_GRANT_KIND,
        "version": OFFLINE_GRANT_VERSION,
    }
    encoded_header = _b64encode(_canonical_json(header))
    encoded_body = _b64encode(_canonical_json(body))
    signed = f"{encoded_header}.{encoded_body}".encode("ascii")
    return f"{signed.decode('ascii')}.{_b64encode(key.sign(signed))}"


def verify_offline_grant_v2(
    token: str,
    public_keys: Mapping[str, Ed25519PublicKey | bytes | str],
    now: int | None = None,
    *,
    check_expiry: bool = True,
) -> dict[str, Any] | None:
    if not isinstance(token, str) or not isinstance(public_keys, Mapping):
        return None
    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        return None
    encoded_header, encoded_body, encoded_signature = parts
    try:
        header = _json_object(_b64decode(encoded_header))
        payload = _json_object(_b64decode(encoded_body))
        signature = _b64decode(encoded_signature)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not _valid_header(header):
        return None
    public_key = public_keys.get(header["kid"])
    if public_key is None:
        return None
    try:
        _public_key(public_key).verify(
            signature, f"{encoded_header}.{encoded_body}".encode("ascii")
        )
    except (InvalidSignature, TypeError, ValueError):
        return None
    if not _valid_payload(payload):
        return None
    current_time = int(time.time()) if now is None else now
    if isinstance(current_time, bool) or not isinstance(current_time, int):
        return None
    if check_expiry and payload["exp"] < current_time:
        return None
    return payload


def public_key_pem(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _grant_payload(payload: Mapping[str, Any], issued_at: int) -> dict[str, Any]:
    required = {
        "actor_user_id",
        "organization_id",
        "branch_id",
        "source_device_id",
        "capabilities",
    }
    if set(payload) != required:
        raise ValueError("offline grant payload fields are invalid")
    values = dict(payload)
    if any(
        not isinstance(values[field], str) or not values[field]
        for field in required - {"capabilities"}
    ):
        raise ValueError("offline grant bindings are invalid")
    capabilities = values["capabilities"]
    if capabilities != [OFFLINE_GRANT_CAPABILITY]:
        raise ValueError("offline grant capability is invalid")
    return {
        "actor_user_id": values["actor_user_id"],
        "branch_id": values["branch_id"],
        "capabilities": capabilities,
        "exp": issued_at + OFFLINE_GRANT_TTL_SECONDS,
        "iat": issued_at,
        "kind": OFFLINE_GRANT_KIND,
        "organization_id": values["organization_id"],
        "source_device_id": values["source_device_id"],
        "version": OFFLINE_GRANT_VERSION,
    }


def _valid_header(header: dict[str, Any]) -> bool:
    return (
        set(header) == {"alg", "kid", "typ", "version"}
        and header.get("alg") == OFFLINE_GRANT_ALGORITHM
        and isinstance(header.get("kid"), str)
        and bool(header["kid"])
        and header.get("typ") == OFFLINE_GRANT_KIND
        and header.get("version") == OFFLINE_GRANT_VERSION
    )


def _valid_payload(payload: dict[str, Any]) -> bool:
    required = {
        "actor_user_id",
        "branch_id",
        "capabilities",
        "exp",
        "iat",
        "kind",
        "organization_id",
        "source_device_id",
        "version",
    }
    if set(payload) != required or payload.get("kind") != OFFLINE_GRANT_KIND:
        return False
    if payload.get("version") != OFFLINE_GRANT_VERSION:
        return False
    if payload.get("capabilities") != [OFFLINE_GRANT_CAPABILITY]:
        return False
    if any(
        not isinstance(payload[field], str) or not payload[field]
        for field in ("actor_user_id", "organization_id", "branch_id", "source_device_id")
    ):
        return False
    if any(
        isinstance(payload[field], bool) or not isinstance(payload[field], int)
        for field in ("iat", "exp")
    ):
        return False
    issued_at = int(payload["iat"])
    expires_at = int(payload["exp"])
    return issued_at <= expires_at <= issued_at + OFFLINE_GRANT_TTL_SECONDS


def _private_key(value: Ed25519PrivateKey | bytes | str) -> Ed25519PrivateKey:
    if isinstance(value, Ed25519PrivateKey):
        return value
    encoded = value.encode("utf-8") if isinstance(value, str) else value
    key = serialization.load_pem_private_key(encoded, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("offline grant private key must be Ed25519")
    return key


def _public_key(value: Ed25519PublicKey | bytes | str) -> Ed25519PublicKey:
    if isinstance(value, Ed25519PublicKey):
        return value
    encoded = value.encode("utf-8") if isinstance(value, str) else value
    key = serialization.load_pem_public_key(encoded)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("offline grant public key must be Ed25519")
    return key


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _json_object(value: bytes) -> dict[str, Any]:
    decoded = json.loads(value.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("offline grant JSON must be an object")
    return decoded


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

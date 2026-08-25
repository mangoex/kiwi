"""Public-key-only verification for the portable PCO-008 offline grant."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Mapping
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

KIND = "offline_grant.v2"
CAPABILITY = "cash.movement.create.v1"
TTL_SECONDS = 2 * 60 * 60


def verify_offline_grant_v2(
    token: str,
    public_keys: Mapping[str, Ed25519PublicKey],
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
    if not (
        set(header) == {"alg", "kid", "typ", "version"}
        and header.get("alg") == "EdDSA"
        and isinstance(header.get("kid"), str)
        and header["kid"]
        and header.get("typ") == KIND
        and header.get("version") == 2
    ):
        return None
    key = public_keys.get(header["kid"])
    if not isinstance(key, Ed25519PublicKey):
        return None
    try:
        key.verify(signature, f"{encoded_header}.{encoded_body}".encode("ascii"))
    except InvalidSignature:
        return None
    if not _valid_payload(payload):
        return None
    current_time = int(time.time()) if now is None else now
    if isinstance(current_time, bool) or not isinstance(current_time, int):
        return None
    if check_expiry and payload["exp"] < current_time:
        return None
    return payload


def parse_public_keyring(values: Mapping[str, str]) -> dict[str, Ed25519PublicKey]:
    parsed: dict[str, Ed25519PublicKey] = {}
    for kid, encoded_key in values.items():
        if not isinstance(kid, str) or not kid or not isinstance(encoded_key, str):
            raise ValueError("gateway public keyring is invalid")
        try:
            key = serialization.load_pem_public_key(encoded_key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("gateway public keyring is invalid") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("gateway public keyring is invalid")
        parsed[kid] = key
    if not parsed:
        raise ValueError("gateway public keyring is invalid")
    return parsed


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
    if set(payload) != required or payload.get("kind") != KIND or payload.get("version") != 2:
        return False
    if payload.get("capabilities") != [CAPABILITY]:
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
    issued_at = cast(int, payload["iat"])
    expires_at = cast(int, payload["exp"])
    return issued_at <= expires_at <= issued_at + TTL_SECONDS


def _json_object(value: bytes) -> dict[str, Any]:
    decoded = json.loads(value.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("offline grant JSON must be an object")
    return decoded


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

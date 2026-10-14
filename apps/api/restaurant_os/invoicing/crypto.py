"""Private fiscal payloads with explicit key ring, authenticated context and no fallback."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from restaurant_os.config import get_settings
from restaurant_os.private_payload_keys import payload_key


def _key(identifier: str) -> bytes:
    return payload_key(identifier)


def seal(payload: dict[str, Any], context: str) -> str:
    identifier = get_settings().fiscal_active_encryption_key_id
    if not identifier:
        raise RuntimeError("fiscal_crypto_unavailable")
    key = _key(identifier)
    plaintext = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, context.encode("utf-8"))
    return json.dumps(
        {
            "version": 1,
            "key_id": identifier,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        },
        separators=(",", ":"),
    )


def unseal(envelope: str, context: str) -> dict[str, Any]:
    try:
        if len(envelope) > 65536:
            raise ValueError("envelope size")
        value = json.loads(envelope)
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "key_id", "nonce", "ciphertext"}
            or type(value["version"]) is not int
            or value["version"] != 1
            or any(not isinstance(value[field], str) for field in ("key_id", "nonce", "ciphertext"))
        ):
            raise ValueError("envelope invalid")
        key = _key(value["key_id"])
        nonce = base64.b64decode(value["nonce"], validate=True)
        if len(nonce) != 12:
            raise ValueError("nonce invalid")
        plaintext = AESGCM(key).decrypt(
            nonce, base64.b64decode(value["ciphertext"], validate=True), context.encode("utf-8")
        )
        payload = json.loads(plaintext)
        if not isinstance(payload, dict):
            raise ValueError("payload invalid")
        return payload
    except Exception:
        raise RuntimeError("fiscal_crypto_unavailable") from None

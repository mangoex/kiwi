"""Bounded encrypted original bytes, with an independent envelope and authenticated scope."""

from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from restaurant_os.config import get_settings
from restaurant_os.private_payload_keys import payload_key
from restaurant_os.supplier_xml_parser import MAX_BYTES

MAX_ENVELOPE = 1572864


def seal_original(original: bytes, context: str) -> str:
    try:
        if type(original) is not bytes or not 1 <= len(original) <= MAX_BYTES:
            raise ValueError("original size")
        identifier = get_settings().fiscal_active_encryption_key_id
        if not identifier:
            raise ValueError("key required")
        nonce = os.urandom(12)
        ciphertext = AESGCM(payload_key(identifier)).encrypt(nonce, original, context.encode())
        value = json.dumps(
            {
                "version": 1,
                "key_id": identifier,
                "nonce": base64.b64encode(nonce).decode(),
                "ciphertext": base64.b64encode(ciphertext).decode(),
            },
            separators=(",", ":"),
        )
        if len(value) > MAX_ENVELOPE:
            raise ValueError("envelope size")
        return value
    except Exception:
        raise RuntimeError("supplier_xml_crypto_unavailable") from None


def unseal_original(envelope: str, context: str) -> bytes:
    try:
        if not isinstance(envelope, str) or len(envelope) > MAX_ENVELOPE:
            raise ValueError("envelope size")
        value = json.loads(envelope)
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "key_id", "nonce", "ciphertext"}
            or type(value["version"]) is not int
            or value["version"] != 1
            or any(not isinstance(value[field], str) for field in ("key_id", "nonce", "ciphertext"))
        ):
            raise ValueError("envelope format")
        nonce = base64.b64decode(value["nonce"], validate=True)
        ciphertext = base64.b64decode(value["ciphertext"], validate=True)
        if len(nonce) != 12 or not 17 <= len(ciphertext) <= MAX_BYTES + 16:
            raise ValueError("cipher size")
        original = AESGCM(payload_key(value["key_id"])).decrypt(nonce, ciphertext, context.encode())
        if not 1 <= len(original) <= MAX_BYTES:
            raise ValueError("original size")
        return original
    except Exception:
        raise RuntimeError("supplier_xml_crypto_unavailable") from None

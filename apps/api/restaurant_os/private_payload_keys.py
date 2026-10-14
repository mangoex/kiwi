"""Provider-neutral resolution of the existing private fiscal/evidence key ring."""

from __future__ import annotations

import base64
import re

from restaurant_os.config import get_settings


def payload_key(identifier: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier):
        raise RuntimeError("fiscal_crypto_unavailable")
    try:
        encoded = get_settings().fiscal_encryption_keys[identifier]
        decoded = base64.b64decode(encoded, validate=True)
        if len(decoded) != 32:
            raise ValueError("key size")
        return decoded
    except (KeyError, ValueError, TypeError):
        raise RuntimeError("fiscal_crypto_unavailable") from None

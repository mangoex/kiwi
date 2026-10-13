"""Validated document identities and public download paths, independent of transport."""

from __future__ import annotations

import re
from collections.abc import Mapping
from uuid import UUID

REMOTE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}", re.ASCII)
FINAL_DOCUMENT_STATES = frozenset({"issued", "cancellation_pending", "cancelled"})


def valid_remote_id(value: object) -> bool:
    return isinstance(value, str) and REMOTE_ID.fullmatch(value) is not None


def valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return parsed.int != 0 and str(parsed) == value.lower()


def document_available(invoice: Mapping[str, object]) -> bool:
    proof = invoice.get("raw_sat_response")
    if not isinstance(proof, Mapping):
        return False
    final = proof.get("status") == "valid" or (
        proof.get("status") == "canceled" and proof.get("cancellation_status") == "accepted"
    )
    return (
        final
        and isinstance(invoice.get("status"), str)
        and invoice.get("status") in FINAL_DOCUMENT_STATES
        and valid_uuid(invoice.get("id"))
        and valid_uuid(invoice.get("uuid_sat"))
        and valid_remote_id(invoice.get("facturapi_invoice_id"))
        and proof.get("id") == invoice.get("facturapi_invoice_id")
        and valid_uuid(proof.get("uuid"))
        and str(proof.get("uuid")).lower() == str(invoice.get("uuid_sat")).lower()
    )

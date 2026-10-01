"""Display historic contact snapshots without looking up or changing current customers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def project_cashier_contact(
    customer: Mapping[str, Any] | None, address: Mapping[str, Any] | None,
) -> dict[str, str]:
    customer = customer or {}
    address = address or {}
    raw_phones = customer.get("phones")
    phones = [
        phone for phone in raw_phones
        if isinstance(phone, dict) and phone.get("status", "active") == "active"
    ] if isinstance(raw_phones, list) else []
    primary = next((phone for phone in phones if phone.get("is_primary") is True), None)
    selected = primary or (phones[0] if phones else {})
    phone_text = (
        _text(selected.get("captured_number")) or _text(selected.get("normalized_number"))
        or _text(customer.get("phone")) or _text(address.get("phone"))
    )
    street = _text(address.get("street"))
    exterior = _text(address.get("exterior_number"))
    interior = _text(address.get("interior_number"))
    street_line = " ".join(part for part in (street, exterior) if part)
    if interior:
        street_line = f"{street_line}, Int. {interior}" if street_line else f"Int. {interior}"
    structured = ", ".join(part for part in (
        street_line, _text(address.get("neighborhood")), _text(address.get("postal_code")),
        _text(address.get("city")), _text(address.get("state")),
    ) if part)
    full_address = _text(address.get("address_text")) or structured or (
        _text(address.get("formatted_address")) or _text(address.get("address_line1"))
    )
    notes = " · ".join(part for part in (
        _text(address.get("cross_streets")), _text(address.get("references")),
        _text(address.get("delivery_instructions")),
    ) if part) or _text(address.get("notes"))
    return {"customer_phone": phone_text, "delivery_address": full_address,
            "delivery_notes": notes}

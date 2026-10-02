"""Exact, non-persistent cash tender preview shared by central and gateway Python."""

from __future__ import annotations

import re
from typing import TypedDict

MAX_SAFE_CENTS = 9_007_199_254_740_991
_AMOUNT = re.compile(r"[0-9]{1,14}(?:[.,][0-9]{1,2})?")


class CashTender(TypedDict):
    received_cents: int
    change_cents: int
    shortfall_cents: int
    can_confirm: bool


def preview_cash_tender(total_cents: int, received_cash: object) -> CashTender:
    """Parse a decimal amount without float, grouping, exponent or currency coercion."""
    if (
        isinstance(total_cents, bool)
        or not isinstance(total_cents, int)
        or not 0 <= total_cents <= MAX_SAFE_CENTS
        or not isinstance(received_cash, str)
    ):
        raise ValueError("cash_received_invalid")
    text = received_cash.strip()
    if not _AMOUNT.fullmatch(text):
        raise ValueError("cash_received_invalid")
    pieces = text.replace(",", ".").split(".")
    received = int(pieces[0]) * 100 + int(pieces[1].ljust(2, "0") if len(pieces) == 2 else "0")
    if received > MAX_SAFE_CENTS:
        raise ValueError("cash_received_invalid")
    return {
        "received_cents": received,
        "change_cents": max(0, received - total_cents),
        "shortfall_cents": max(0, total_cents - received),
        "can_confirm": received >= total_cents,
    }

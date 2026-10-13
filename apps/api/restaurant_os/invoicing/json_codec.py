"""Bounded JSON encoding of exact fiscal decimals, without a float conversion."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_DEPTH = 64
MAX_NUMBER_DIGITS = 128
STRING_CHUNK_CHARS = 4096


def encode_json(value: Any) -> bytes:
    """Decimal values become JSON numbers; strings remain escaped JSON strings.

    Finite legacy floats retain their existing JSON representation. This serializer
    does not establish the fiscal sufficiency or arithmetic of its caller's data.
    """
    body = bytearray()
    active: set[int] = set()

    def append(text: str) -> None:
        encoded = text.encode("utf-8")
        if len(body) + len(encoded) > MAX_REQUEST_BYTES:
            raise ValueError("fiscal_json_size_invalid")
        body.extend(encoded)

    def encode(item: Any, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise ValueError("fiscal_json_depth_invalid")
        if item is None or type(item) is bool:
            append(json.dumps(item))
        elif type(item) is str:
            if len(item) > MAX_REQUEST_BYTES:
                raise ValueError("fiscal_json_size_invalid")
            append('"')
            for offset in range(0, len(item), STRING_CHUNK_CHARS):
                # Escape complete code points in bounded chunks. A control-heavy
                # string must not allocate its entire expanded representation
                # before the cumulative UTF-8 limit can reject it.
                escaped = json.dumps(item[offset : offset + STRING_CHUNK_CHARS], ensure_ascii=False)
                append(escaped[1:-1])
            append('"')
        elif type(item) is int:
            if item.bit_length() > 426:
                raise ValueError("fiscal_json_number_invalid")
            number = str(item)
            if len(number.lstrip("-")) > MAX_NUMBER_DIGITS:
                raise ValueError("fiscal_json_number_invalid")
            append(number)
        elif type(item) is float:
            append(json.dumps(item, allow_nan=False))
        elif type(item) is Decimal:
            if not item.is_finite():
                raise ValueError("fiscal_json_number_invalid")
            parts = item.as_tuple()
            exponent = parts.exponent
            if (
                not isinstance(exponent, int)
                or not -128 <= exponent <= 128
                or len(parts.digits) > MAX_NUMBER_DIGITS
            ):
                raise ValueError("fiscal_json_number_invalid")
            append(str(item))
        elif type(item) in {dict, list, tuple}:
            identifier = id(item)
            if identifier in active:
                raise ValueError("fiscal_json_cycle_invalid")
            active.add(identifier)
            try:
                is_object = type(item) is dict
                append("{" if is_object else "[")
                for index, entry in enumerate(item):
                    if index:
                        append(",")
                    if is_object:
                        if type(entry) is not str:
                            raise ValueError("fiscal_json_key_invalid")
                        encode(entry, depth + 1)
                        append(":")
                        encode(item[entry], depth + 1)
                    else:
                        encode(entry, depth + 1)
                append("}" if is_object else "]")
            finally:
                active.remove(identifier)
        else:
            raise TypeError("fiscal_json_type_invalid")

    encode(value, 0)
    return bytes(body)

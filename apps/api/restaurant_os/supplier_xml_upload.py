"""Bounded raw request reading outside transactional authority locks."""

from __future__ import annotations

import asyncio

from starlette.requests import ClientDisconnect, Request

from restaurant_os.operations import BusinessError
from restaurant_os.supplier_xml_parser import MAX_BYTES

UPLOAD_DEADLINE_SECONDS = 5


async def read_original(request: Request) -> bytes:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/xml"
    ):
        raise BusinessError("xml_content_type_invalid", "Upload raw application/xml")
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise BusinessError("xml_compression_unsupported", "Compressed XML is not accepted")
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isascii() or not declared.isdigit() or len(declared) > 16:
            raise BusinessError("xml_content_length_invalid", "Content length is invalid")
        if not 1 <= int(declared) <= MAX_BYTES:
            raise BusinessError("xml_size_exceeded", "XML size is invalid")

    async def collect() -> bytes:
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise BusinessError("xml_size_exceeded", "XML size is invalid")
            data.extend(chunk)
        if not data or (declared is not None and len(data) != int(declared)):
            raise BusinessError("xml_content_length_invalid", "XML body is incomplete")
        return bytes(data)

    try:
        return await asyncio.wait_for(collect(), timeout=UPLOAD_DEADLINE_SECONDS)
    except asyncio.TimeoutError:
        raise BusinessError("xml_upload_timeout", "XML upload exceeded its deadline") from None
    except ClientDisconnect:
        raise BusinessError("xml_content_length_invalid", "XML body is incomplete") from None


async def require_empty_body(request: Request) -> None:
    """Resolve takes its key from a header; never parse or echo a JSON body."""
    length = request.headers.get("content-length")
    if length not in {None, "0"}:
        raise BusinessError("supplier_xml_schema_invalid", "Resolve requires an empty body")

    async def check() -> None:
        async for chunk in request.stream():
            if chunk:
                raise BusinessError("supplier_xml_schema_invalid", "Resolve requires an empty body")

    try:
        await asyncio.wait_for(check(), timeout=UPLOAD_DEADLINE_SECONDS)
    except asyncio.TimeoutError:
        raise BusinessError("xml_upload_timeout", "Request exceeded its deadline") from None
    except ClientDisconnect:
        raise BusinessError("supplier_xml_schema_invalid", "Request is incomplete") from None

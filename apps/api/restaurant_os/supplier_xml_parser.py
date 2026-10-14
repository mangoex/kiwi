"""Bounded syntactic XML extraction; never fiscal validation or transactional import."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from xml.parsers import expat as pyexpat

MAX_BYTES = 1048576
MAX_NODES = 10000
MAX_DEPTH = 32
MAX_ATTRIBUTES = 128
MAX_NAME = 512
MAX_ATTRIBUTE_VALUE = 32768


class SupplierXmlParseError(ValueError):
    """Stable code only; untrusted parser messages never escape this boundary."""


class _BoundedBuilder(ET.TreeBuilder):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.nodes = 0
        self.text_bytes = 0
        self.namespaces = 0

    def start_ns(self, prefix: str | None, uri: str) -> None:
        self.namespaces += 1
        if (
            self.namespaces > MAX_ATTRIBUTES
            or len(prefix or "") > MAX_NAME
            or len(uri) > MAX_ATTRIBUTE_VALUE
        ):
            raise SupplierXmlParseError("xml_structure_limit")

    def start(self, tag: str, attrs: dict[str, str]) -> ET.Element:
        self.namespaces = 0
        self.depth += 1
        self.nodes += 1
        if (
            self.depth > MAX_DEPTH
            or self.nodes > MAX_NODES
            or len(tag) > MAX_NAME
            or len(attrs) > MAX_ATTRIBUTES
            or any(
                len(key) > MAX_NAME or len(value) > MAX_ATTRIBUTE_VALUE
                for key, value in attrs.items()
            )
        ):
            raise SupplierXmlParseError("xml_structure_limit")
        return super().start(tag, attrs)

    def end(self, tag: str) -> ET.Element:
        value = super().end(tag)
        self.depth -= 1
        return value

    def data(self, data: str) -> None:
        self.text_bytes += len(data.encode("utf-8"))
        if self.text_bytes > MAX_BYTES:
            raise SupplierXmlParseError("xml_text_limit")
        super().data(data)

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise SupplierXmlParseError("xml_doctype_forbidden")

    def pi(self, target: str, text: str | None = None) -> ET.Element:
        raise SupplierXmlParseError("xml_processing_instruction_forbidden")


def parse_supplier_xml(original: bytes) -> ET.Element:
    """Return an in-memory tree within fixed limits, with no I/O or partial results."""
    if type(original) is not bytes or not original:
        raise SupplierXmlParseError("xml_input_invalid")
    if len(original) > MAX_BYTES:
        raise SupplierXmlParseError("xml_size_exceeded")
    version = re.fullmatch(r"expat_(\d+)\.(\d+)\.(\d+)", pyexpat.EXPAT_VERSION)
    if version is None or tuple(int(value) for value in version.groups()) < (2, 7, 2):
        raise SupplierXmlParseError("xml_parser_unavailable")
    parser = ET.XMLParser(target=_BoundedBuilder())
    try:
        parser.feed(original)
        root = parser.close()
    except SupplierXmlParseError:
        raise
    except (ET.ParseError, UnicodeError, LookupError, ValueError):
        raise SupplierXmlParseError("xml_invalid") from None
    if not isinstance(root, ET.Element):
        raise SupplierXmlParseError("xml_invalid")
    return root

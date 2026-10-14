"""Syntactic XML boundary; no claim of fiscal validation or import completion."""

from __future__ import annotations

import gzip
import importlib
from unittest.mock import patch

import pytest


def parser():
    return importlib.import_module("restaurant_os.supplier_xml_parser")


def test_benign_xml_and_utf16_are_extraction_only():
    module = parser()
    source = '<root xmlns="urn:test"><child amount="0.29">México</child></root>'
    for encoded in (source.encode(), source.encode("utf-16")):
        root = module.parse_supplier_xml(encoded)
        assert root.tag == "{urn:test}root"
        assert root[0].attrib == {"amount": "0.29"}
        assert root[0].text == "México"


@pytest.mark.parametrize(
    "source",
    [
        '<!DOCTYPE root [<!ENTITY x "secret">]><root>&x;</root>',
        '<!DOCTYPE root SYSTEM "http://127.0.0.1:1/private"><root/>',
        '<!DOCTYPE root [<!ENTITY x SYSTEM "file:///private">]><root>&x;</root>',
        '<!DOCTYPE root [<!ENTITY a "123"><!ENTITY b "&a;&a;">]><root>&b;</root>',
    ],
)
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_any_doctype_is_rejected_before_entities(source, encoding):
    module = parser()
    with (
        patch("socket.socket", side_effect=AssertionError("network")),
        patch("builtins.open", side_effect=AssertionError("file")),
    ):
        with pytest.raises(module.SupplierXmlParseError, match="xml_doctype_forbidden"):
            module.parse_supplier_xml(source.encode(encoding))


@pytest.mark.parametrize(
    "source", [b"<?xml-stylesheet href='http://invalid/'?><root/>", b"<root><?x y?></root>"]
)
def test_processing_instruction_rejected(source):
    module = parser()
    with pytest.raises(module.SupplierXmlParseError, match="xml_processing_instruction_forbidden"):
        module.parse_supplier_xml(source)


@pytest.mark.parametrize(
    "source",
    [
        None,
        "<root/>",
        bytearray(b"<root/>"),
        b"",
        b"<root>",
        b"<x/><y/>",
        gzip.compress(b"<root/>", mtime=0),
    ],
)
def test_invalid_input_never_returns_partial_tree_or_payload(source):
    module = parser()
    with pytest.raises(module.SupplierXmlParseError) as error:
        module.parse_supplier_xml(source)
    assert str(error.value).startswith("xml_")
    assert "root" not in str(error.value)


def test_size_bound_before_parser():
    module = parser()
    exact = b"<root>" + b"x" * (1048576 - 13) + b"</root>"
    assert len(exact) == 1048576
    assert module.parse_supplier_xml(exact).tag == "root"
    with pytest.raises(module.SupplierXmlParseError, match="xml_size_exceeded"):
        module.parse_supplier_xml(exact + b" ")


def test_depth_and_node_boundaries():
    module = parser()
    assert module.parse_supplier_xml(b"<r>" * 32 + b"</r>" * 32).tag == "r"
    with pytest.raises(module.SupplierXmlParseError, match="xml_structure_limit"):
        module.parse_supplier_xml(b"<r>" * 33 + b"</r>" * 33)
    assert len(module.parse_supplier_xml(b"<r>" + b"<x/>" * 9999 + b"</r>")) == 9999
    with pytest.raises(module.SupplierXmlParseError, match="xml_structure_limit"):
        module.parse_supplier_xml(b"<r>" + b"<x/>" * 10000 + b"</r>")


def test_attribute_boundaries():
    module = parser()
    attrs = " ".join(f"x{i}='v'" for i in range(128))
    assert len(module.parse_supplier_xml(f"<r {attrs}/>".encode()).attrib) == 128
    with pytest.raises(module.SupplierXmlParseError, match="xml_structure_limit"):
        module.parse_supplier_xml(f"<r {attrs} extra='v'/>".encode())
    assert module.parse_supplier_xml(("<r a='" + "v" * 32768 + "'/>").encode()).attrib["a"]
    with pytest.raises(module.SupplierXmlParseError, match="xml_structure_limit"):
        module.parse_supplier_xml(("<r a='" + "v" * 32769 + "'/>").encode())


def test_decoded_text_limit_in_utf16():
    module = parser()
    # U+20AC occupies 2 source bytes in UTF-16 and 3 decoded UTF-8 bytes.
    with pytest.raises(module.SupplierXmlParseError, match="xml_text_limit"):
        module.parse_supplier_xml(("<r>" + "€" * 349526 + "</r>").encode("utf-16"))


def test_namespace_declarations_are_bounded_before_start():
    module = parser()
    declarations = " ".join(f"xmlns:x{i}='urn:{i}'" for i in range(128))
    assert module.parse_supplier_xml(f"<r {declarations}/>".encode()).tag == "r"
    with pytest.raises(module.SupplierXmlParseError, match="xml_structure_limit"):
        module.parse_supplier_xml(f"<r {declarations} xmlns:extra='urn:extra'/>".encode())
    with pytest.raises(module.SupplierXmlParseError, match="xml_structure_limit"):
        module.parse_supplier_xml(("<r xmlns:x='urn:" + "a" * 32769 + "'/>").encode())


@pytest.mark.parametrize("version", ["expat_2.6.4", "expat_2.7.1", "unknown", "expat_2.7.2-dev"])
def test_unsupported_engine_fails_closed(monkeypatch, version):
    module = parser()
    monkeypatch.setattr(module.pyexpat, "EXPAT_VERSION", version)
    with pytest.raises(module.SupplierXmlParseError, match="xml_parser_unavailable"):
        module.parse_supplier_xml(b"<root/>")

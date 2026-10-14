"""Synthetic unverified header capture, not a valid fiscal invoice fixture."""

import hashlib
import importlib
from dataclasses import FrozenInstanceError

import pytest

SOURCE = b"""<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0">
<cfdi:Emisor Rfc="AAA010101AAA"/><cfdi:Receptor Rfc="BBB010101BBB"/>
<cfdi:Complemento><t:TimbreFiscalDigital xmlns:t="http://www.sat.gob.mx/TimbreFiscalDigital"
 Version="1.1" UUID="01234567-89ab-cdef-0123-456789abcdef"/></cfdi:Complemento>
</cfdi:Comprobante>"""


def module():
    return importlib.import_module("restaurant_os.supplier_cfdi_identity")


def test_capture_is_immutable_unverified_and_byte_hash_is_original():
    api = module()
    value = api.capture_supplier_cfdi_identity(SOURCE, "BBB010101BBB")
    assert value.uuid == "01234567-89AB-CDEF-0123-456789ABCDEF"
    assert value.original_sha256 == hashlib.sha256(SOURCE).hexdigest()
    assert value.fiscal_validation == "unverified"
    with pytest.raises(FrozenInstanceError):
        value.uuid = "changed"
    assert (
        api.capture_supplier_cfdi_identity(SOURCE + b" ", "BBB010101BBB").original_sha256
        != value.original_sha256
    )


@pytest.mark.parametrize("receiver", [None, "", "BAD", "bbb010101bbb", "CCC010101CCC"])
def test_unknown_or_foreign_receiver_never_guessed(receiver):
    api = module()
    with pytest.raises(api.SupplierXmlParseError) as error:
        api.capture_supplier_cfdi_identity(SOURCE, receiver)
    assert "BBB" not in str(error.value) and "CCC" not in str(error.value)


@pytest.mark.parametrize(
    "old,new",
    [
        (b"cfd/4", b"cfd/3"),
        (b'Version="4.0"', b'Version="3.3"'),
        (b'Version="1.1"', b'Version="1.0"'),
        (b"01234567-89ab-cdef-0123-456789abcdef", b"not-a-uuid"),
        (
            b'<cfdi:Emisor Rfc="AAA010101AAA"/>',
            b'<cfdi:Emisor Rfc="AAA010101AAA"/><cfdi:Emisor Rfc="AAA010101AAA"/>',
        ),
        (b'<cfdi:Receptor Rfc="BBB010101BBB"/>', b""),
        (b"http://www.sat.gob.mx/TimbreFiscalDigital", b"urn:fake"),
    ],
)
def test_incompatible_ambiguous_or_incomplete_identity_rejected(old, new):
    api = module()
    with pytest.raises(api.SupplierXmlParseError):
        api.capture_supplier_cfdi_identity(SOURCE.replace(old, new), "BBB010101BBB")

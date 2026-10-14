"""Capture declared identity only; never SAT validation, authorization or accounting."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Literal

from restaurant_os.supplier_xml_parser import SupplierXmlParseError, parse_supplier_xml

CFDI = "{http://www.sat.gob.mx/cfd/4}"
TFD = "{http://www.sat.gob.mx/TimbreFiscalDigital}"
RFC = re.compile(r"[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}")
FISCAL_UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


@dataclass(frozen=True)
class UnverifiedCfdiIdentity:
    uuid: str
    issuer_tax_id: str
    receiver_tax_id: str
    original_sha256: str
    capture_profile: Literal["cfdi4_tfd11_identity_v1"] = field(
        default="cfdi4_tfd11_identity_v1", init=False
    )
    fiscal_validation: Literal["unverified"] = field(default="unverified", init=False)


def _one(parent: ET.Element, name: str) -> ET.Element:
    found = parent.findall(name)
    if len(found) != 1:
        raise SupplierXmlParseError("xml_identity_ambiguous")
    return found[0]


def _declared_rfc(element: ET.Element) -> str:
    value = element.get("Rfc", "")
    if RFC.fullmatch(value) is None:
        raise SupplierXmlParseError("xml_identity_invalid")
    return value


def capture_supplier_cfdi_identity(original: bytes, receiver_tax_id: str) -> UnverifiedCfdiIdentity:
    """Consumer must load the receiver under current authority; a string grants no permission."""
    if not isinstance(receiver_tax_id, str) or RFC.fullmatch(receiver_tax_id) is None:
        raise SupplierXmlParseError("xml_receiver_unconfigured")
    root = parse_supplier_xml(original)
    if root.tag != CFDI + "Comprobante" or root.get("Version") != "4.0":
        raise SupplierXmlParseError("xml_profile_unsupported")
    issuer = _declared_rfc(_one(root, CFDI + "Emisor"))
    receiver = _declared_rfc(_one(root, CFDI + "Receptor"))
    if receiver != receiver_tax_id:
        raise SupplierXmlParseError("xml_receiver_mismatch")
    stamp = _one(_one(root, CFDI + "Complemento"), TFD + "TimbreFiscalDigital")
    if len(list(root.iter(TFD + "TimbreFiscalDigital"))) != 1:
        raise SupplierXmlParseError("xml_identity_ambiguous")
    if stamp.get("Version") != "1.1":
        raise SupplierXmlParseError("xml_profile_unsupported")
    identifier = stamp.get("UUID", "")
    if FISCAL_UUID.fullmatch(identifier) is None:
        raise SupplierXmlParseError("xml_identity_invalid")
    return UnverifiedCfdiIdentity(
        uuid=identifier.upper(),
        issuer_tax_id=issuer,
        receiver_tax_id=receiver,
        original_sha256=hashlib.sha256(original).hexdigest(),
    )

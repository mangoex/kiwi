"""PUR-AI-CAPTURE-001: Multimodal and document-assisted purchase draft extraction."""

from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.orm import Session

from restaurant_os.config import get_settings
from restaurant_os.operations import (
    BusinessError,
    _actor_user_id,
    authorize_branch_scope,
    list_purchase_presentations,
    list_suppliers,
)
from restaurant_os.supplier_xml_parser import SupplierXmlParseError, parse_supplier_xml

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_XML_BYTES = 1024 * 1024
MAX_RAW_TEXT_CHARS = 10_000
MAX_EXTRACTED_LINES = 200
MAX_SAFE_DECIMAL = Decimal("999999999.99")
TWO_DECIMALS = Decimal("0.01")

EXTRACT_KEYS = {"branch_id", "raw_text", "file_base64", "mime_type", "filename"}

_SAT_PAYMENT_MAP = {
    "01": "cash",
    "02": "other",
    "03": "transfer",
    "04": "card",
    "28": "card",
    "99": "other",
}

_TEXT_PAYMENT_MAP = {
    "efectivo": "cash",
    "cash": "cash",
    "caja": "cash",
    "transferencia": "transfer",
    "transfer": "transfer",
    "spei": "transfer",
    "tarjeta": "card",
    "card": "card",
    "debito": "card",
    "credito": "card",
    "otro": "other",
    "other": "other",
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_token_string(value: str) -> str:
    lowered = _strip_accents(value.lower())
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def _similarity(left: str, right: str) -> float:
    norm_left = _normalize_token_string(left)
    norm_right = _normalize_token_string(right)
    if not norm_left or not norm_right:
        return 0.0
    if norm_left == norm_right:
        return 1.0
    if norm_left in norm_right or norm_right in norm_left:
        shorter = min(len(norm_left), len(norm_right))
        longer = max(len(norm_left), len(norm_right))
        if shorter >= 4:
            return max(0.84, shorter / longer)
    left_tokens = set(norm_left.split())
    right_tokens = set(norm_right.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens), 1)
    seq = SequenceMatcher(None, norm_left, norm_right).ratio()
    return max(seq, overlap * 0.92)


def _format_two_decimals(value: Decimal) -> str:
    return str(value.quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP))


def _parse_bounded_decimal(
    raw: Any, *, allow_zero: bool = True, max_scale: int = 6
) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    text = str(raw).strip()
    if text.startswith("$"):
        text = text[1:].strip()
    if not text:
        return None
    if "," in text:
        if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
            text = text.replace(",", "")
        else:
            return None
    if not re.fullmatch(rf"-?\d+(?:\.\d{{1,{max_scale}}})?", text):
        return None
    try:
        dec = Decimal(text)
    except InvalidOperation:
        return None
    if not dec.is_finite() or dec > MAX_SAFE_DECIMAL:
        return None
    if allow_zero:
        if dec < Decimal("0"):
            return None
    elif dec <= Decimal("0"):
        return None
    return dec


def _normalize_date(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    cleaned = raw.strip()
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})", cleaned)
    if iso_match:
        return iso_match.group(1)
    dmy_match = re.match(r"^(\d{2})[/-](\d{2})[/-](\d{4})$", cleaned)
    if dmy_match:
        day, month, year = dmy_match.groups()
        return f"{year}-{month}-{day}"
    return ""


def _normalize_payment_method(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "cash"
    token = _normalize_token_string(raw)
    for key, mapped in _TEXT_PAYMENT_MAP.items():
        if key in token.split() or key == token:
            return mapped
    if raw.strip() in _SAT_PAYMENT_MAP:
        return _SAT_PAYMENT_MAP[raw.strip()]
    return "cash"


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _attr_ci(elem: ET.Element, *names: str) -> str:
    lower_map = {k.lower(): v for k, v in elem.attrib.items()}
    for name in names:
        val = lower_map.get(name.lower())
        if val is not None and val.strip():
            return val.strip()
    return ""


def _extract_from_cfdi_xml(raw_bytes: bytes) -> dict[str, Any]:
    if len(raw_bytes) > MAX_XML_BYTES:
        raise BusinessError(
            "purchase_extract_size_exceeded",
            "El archivo XML CFDI excede el límite de 1 MB.",
        )
    try:
        root = parse_supplier_xml(raw_bytes)
    except SupplierXmlParseError as exc:
        raise BusinessError(
            "purchase_extract_invalid_file",
            "El archivo XML CFDI no es válido o contiene directivas no permitidas.",
        ) from exc

    if _local_tag(root.tag).lower() != "comprobante":
        raise BusinessError(
            "purchase_extract_invalid_file",
            "El XML no corresponde a un Comprobante CFDI.",
        )

    serie = _attr_ci(root, "Serie")
    folio_num = _attr_ci(root, "Folio")
    folio = f"{serie}-{folio_num}" if serie and folio_num else (folio_num or serie)
    document_date = _normalize_date(_attr_ci(root, "Fecha"))
    forma_pago = _attr_ci(root, "FormaPago")
    payment_method = _SAT_PAYMENT_MAP.get(forma_pago, "transfer" if forma_pago else "cash")

    supplier_name = ""
    supplier_tax_id = ""
    raw_lines: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    line_idx = 0
    for elem in root.iter():
        tag = _local_tag(elem.tag).lower()
        if tag == "emisor" and not (supplier_name or supplier_tax_id):
            supplier_tax_id = _attr_ci(elem, "Rfc")
            supplier_name = _attr_ci(elem, "Nombre")
        elif tag == "concepto":
            line_idx += 1
            desc = _attr_ci(elem, "Descripcion")
            sku = _attr_ci(elem, "NoIdentificacion", "ClaveProdServ")
            qty_str = _attr_ci(elem, "Cantidad")
            unit_price_str = _attr_ci(elem, "ValorUnitario")
            discount_str = _attr_ci(elem, "Descuento") or "0"

            tax_total = Decimal("0")
            for child in elem.iter():
                if _local_tag(child.tag).lower() == "traslado":
                    imp_str = _attr_ci(child, "Importe")
                    if imp_str:
                        parsed_tax = _parse_bounded_decimal(imp_str, allow_zero=True)
                        if parsed_tax is not None:
                            tax_total += parsed_tax

            raw_lines.append(
                {
                    "line_number": line_idx,
                    "description": desc,
                    "sku": sku,
                    "quantity": qty_str,
                    "unit_price": unit_price_str,
                    "discount": discount_str,
                    "tax": str(tax_total),
                }
            )

    return {
        "source_kind": "xml_cfdi",
        "supplier_name": supplier_name,
        "supplier_tax_id": supplier_tax_id,
        "folio": folio,
        "document_date": document_date,
        "delivered_by_name": "",
        "payment_method": payment_method,
        "notes": "",
        "raw_lines": raw_lines,
        "warnings": warnings,
    }


def _extract_text_from_pdf_bytes(raw_bytes: bytes) -> str:
    fragments: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw_bytes, re.DOTALL):
        stream_data = match.group(1)
        decoded_stream = stream_data
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                decompressed = zlib.decompress(stream_data, wbits)
                if len(decompressed) <= MAX_FILE_BYTES:
                    decoded_stream = decompressed
                    break
            except zlib.error:
                continue
        text_chunk = decoded_stream.decode("latin-1", errors="ignore")
        literals = re.findall(r"\(([^()]*)\)\s*T[jJ]", text_chunk)
        if literals:
            fragments.extend(literals)
        else:
            array_matches = re.findall(r"\[(.*?)\]\s*TJ", text_chunk, re.DOTALL)
            for arr in array_matches:
                parts = re.findall(r"\(([^()]*)\)", arr)
                if parts:
                    fragments.append("".join(parts))
    return "\n".join(fragment.strip() for fragment in fragments if fragment.strip())


def _parse_structured_or_natural_text(raw_text: str) -> dict[str, Any]:
    supplier_name = ""
    supplier_tax_id = ""
    folio = ""
    document_date = ""
    delivered_by_name = ""
    payment_method = "cash"
    notes = ""
    raw_lines: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        clean = raw_line.strip()
        if not clean:
            continue

        header_match = re.match(
            r"^(proveedor|emisor|rfc|folio|factura|nota|fecha|entreg[oó]|recibi[oó]\s+de|pago|metodo\s+de\s+pago|notas?)\s*:\s*(.+)$",
            clean,
            re.IGNORECASE,
        )
        if header_match and "|" not in clean:
            key = _strip_accents(header_match.group(1).lower())
            val = header_match.group(2).strip()
            if key in {"proveedor", "emisor"}:
                supplier_name = val
            elif key == "rfc":
                supplier_tax_id = val.upper()
            elif key in {"folio", "factura", "nota"}:
                folio = val
            elif key == "fecha":
                document_date = _normalize_date(val) or document_date
            elif key.startswith("entrego") or key.startswith("recibio"):
                delivered_by_name = val
            elif key.startswith("pago") or key.startswith("metodo"):
                payment_method = _normalize_payment_method(val)
            elif key.startswith("nota"):
                notes = val
            continue

        if "|" in clean:
            parts = [part.strip() for part in clean.split("|")]
            if len(parts) < 3 or not parts[0]:
                warnings.append(
                    {"line_number": line_number, "code": "unparsed_line", "raw": clean[:160]}
                )
                continue
            desc = parts[0]
            qty_token = parts[1].split()[0] if parts[1] else ""
            price_token = parts[2]
            discount_token = parts[3] if len(parts) >= 4 and parts[3] else "0"
            tax_token = parts[4] if len(parts) >= 5 and parts[4] else "0"
            raw_lines.append(
                {
                    "line_number": line_number,
                    "description": desc,
                    "sku": "",
                    "quantity": qty_token,
                    "unit_price": price_token,
                    "discount": discount_token,
                    "tax": tax_token,
                }
            )
            continue

        bullet_stripped = re.sub(r"^[-•*]\s*", "", clean)
        nat_match = re.match(
            r"^(?P<qty>-?\d+(?:\.\d{1,6})?)\s*(?:x\s+)?(?P<desc>.+?)\s+(?:(?P<unit_marker>a|@)\s*)?\$?(?P<amount>-?\d+(?:,\d{3})*(?:\.\d{1,4})?)\s*(?P<mode>c/u|cu|unitario|total)?$",
            bullet_stripped,
            re.IGNORECASE,
        )
        if nat_match:
            qty_str = nat_match.group("qty")
            desc = nat_match.group("desc").strip(" -:")
            amount_str = nat_match.group("amount")
            unit_marker = (nat_match.group("unit_marker") or "").lower()
            mode = (nat_match.group("mode") or "").lower()

            qty_dec = _parse_bounded_decimal(qty_str, allow_zero=False)
            amt_dec = _parse_bounded_decimal(amount_str, allow_zero=True)
            if qty_dec is not None and amt_dec is not None:
                is_unit_price = bool(unit_marker) or mode in {"c/u", "cu", "unitario"}
                unit_price_dec = (
                    amt_dec
                    if is_unit_price
                    else (amt_dec / qty_dec).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
                )
                raw_lines.append(
                    {
                        "line_number": line_number,
                        "description": desc,
                        "sku": "",
                        "quantity": str(qty_dec),
                        "unit_price": str(unit_price_dec),
                        "discount": "0",
                        "tax": "0",
                    }
                )
            else:
                warnings.append(
                    {
                        "line_number": line_number,
                        "code": "invalid_line_amount",
                        "raw": clean[:160],
                    }
                )
            continue

        warnings.append(
            {"line_number": line_number, "code": "unparsed_line", "raw": clean[:160]}
        )

    return {
        "source_kind": "text_list",
        "supplier_name": supplier_name,
        "supplier_tax_id": supplier_tax_id,
        "folio": folio,
        "document_date": document_date,
        "delivered_by_name": delivered_by_name,
        "payment_method": payment_method,
        "notes": notes,
        "raw_lines": raw_lines,
        "warnings": warnings,
    }


def _detect_and_validate_file(
    file_base64: str, mime_type: str, filename: str
) -> tuple[bytes, str, str]:
    b64_clean = file_base64.strip()
    if b64_clean.startswith("data:") and "," in b64_clean:
        header, b64_clean = b64_clean.split(",", 1)
        if not mime_type:
            mime_match = re.match(r"^data:([^;]+);base64$", header.strip(), re.IGNORECASE)
            if mime_match:
                mime_type = mime_match.group(1).lower()
    b64_clean = re.sub(r"\s+", "", b64_clean)
    if not b64_clean:
        raise BusinessError("purchase_extract_invalid_file", "El archivo adjunto está vacío.")
    try:
        raw_bytes = base64.b64decode(b64_clean, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BusinessError(
            "purchase_extract_invalid_file", "La codificación base64 del archivo es inválida."
        ) from exc

    if not raw_bytes:
        raise BusinessError("purchase_extract_invalid_file", "El archivo adjunto está vacío.")
    if len(raw_bytes) > MAX_FILE_BYTES:
        raise BusinessError(
            "purchase_extract_size_exceeded",
            "El archivo excede el tamaño máximo permitido de 5 MB.",
        )

    normalized_mime = mime_type.strip().lower()
    lower_name = filename.strip().lower()
    if normalized_mime in {"", "application/octet-stream"}:
        if lower_name.endswith(".xml"):
            normalized_mime = "application/xml"
        elif lower_name.endswith(".pdf"):
            normalized_mime = "application/pdf"
        elif lower_name.endswith(".png"):
            normalized_mime = "image/png"
        elif lower_name.endswith((".jpg", ".jpeg")):
            normalized_mime = "image/jpeg"
        elif lower_name.endswith(".webp"):
            normalized_mime = "image/webp"

    if normalized_mime in {"application/xml", "text/xml"}:
        return raw_bytes, "application/xml", b64_clean
    if normalized_mime == "application/pdf":
        if not raw_bytes.startswith(b"%PDF-"):
            raise BusinessError(
                "purchase_extract_invalid_file",
                "El archivo PDF no contiene una cabecera %PDF- válida.",
            )
        return raw_bytes, "application/pdf", b64_clean
    if normalized_mime == "image/png":
        if not raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise BusinessError(
                "purchase_extract_invalid_file",
                "El archivo PNG no contiene una firma válida.",
            )
        return raw_bytes, "image/png", b64_clean
    if normalized_mime in {"image/jpeg", "image/jpg"}:
        if not raw_bytes.startswith(b"\xff\xd8\xff"):
            raise BusinessError(
                "purchase_extract_invalid_file",
                "El archivo JPEG no contiene una firma válida.",
            )
        return raw_bytes, "image/jpeg", b64_clean
    if normalized_mime == "image/webp":
        if len(raw_bytes) < 12 or not raw_bytes.startswith(b"RIFF") or raw_bytes[8:12] != b"WEBP":
            raise BusinessError(
                "purchase_extract_invalid_file",
                "El archivo WEBP no contiene una firma válida.",
            )
        return raw_bytes, "image/webp", b64_clean

    raise BusinessError(
        "purchase_extract_invalid_file",
        "Formato no soportado. Sube una imagen (PNG, JPG, WEBP), PDF o XML CFDI.",
    )


def _call_openrouter_extraction(
    *,
    b64_clean: str | None,
    mime_type: str | None,
    filename: str,
    raw_text: str,
    suppliers: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    api_key = (settings.openrouter_api_key or "").strip()
    if not api_key:
        raise BusinessError(
            "purchase_ai_provider_unavailable",
            "La extracción multimodal por IA requiere configurar OPENROUTER_API_KEY.",
        )

    supplier_hints = [
        f"{s.get('commercial_name', '')} (RFC: {s.get('tax_id') or 'N/A'})"
        for s in suppliers[:60]
    ]
    presentation_hints = [
        (
            f"{p.get('code', '')}: {p.get('name', '')} — "
            f"Insumo: {p.get('item_name', '')} ({p.get('item_sku', '')})"
        )
        for p in presentations[:120]
    ]

    system_prompt = (
        "Eres un asistente contable y operativo para RestaurantOS. "
        "Extrae con exactitud los datos del documento de compra, factura, ticket "
        "o lista escrita en papel. Reglas estrictas:\n"
        "1. NO inventes partidas, cantidades ni precios que no aparezcan en el documento.\n"
        "2. Expresa quantity, unit_price, discount y tax como cadenas decimales "
        "exactas sin símbolo de moneda.\n"
        "3. Si en una lista o ticket sólo aparece el importe total del renglón y "
        "la cantidad, calcula unit_price = importe / cantidad.\n"
        "4. Si un concepto coincide claramente con una presentación del catálogo "
        "provisto, incluye su código en sku.\n"
        "5. payment_method debe ser uno de: cash, transfer, card, other.\n"
        f"Proveedores activos en sucursal: {'; '.join(supplier_hints) or 'Ninguno'}\n"
        f"Presentaciones de compra en sucursal: {'; '.join(presentation_hints) or 'Ninguna'}"
    )

    user_content: list[dict[str, Any]] = []
    if raw_text.strip():
        user_content.append({"type": "text", "text": f"Texto de compra:\n{raw_text.strip()}"})
    else:
        user_content.append(
            {
                "type": "text",
                "text": "Extrae cabecera y partidas de este comprobante o lista de compra.",
            }
        )

    if b64_clean and mime_type:
        data_url = f"data:{mime_type};base64,{b64_clean}"
        if mime_type == "application/pdf":
            user_content.append(
                {
                    "type": "file",
                    "file": {
                        "filename": filename or "documento.pdf",
                        "file_data": data_url,
                    },
                }
            )
        else:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                }
            )

    schema = {
        "name": "purchase_document_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "supplier_name": {"type": "string"},
                "supplier_tax_id": {"type": "string"},
                "folio": {"type": "string"},
                "document_date": {"type": "string"},
                "delivered_by_name": {"type": "string"},
                "payment_method": {
                    "type": "string",
                    "enum": ["cash", "transfer", "card", "other"],
                },
                "notes": {"type": "string"},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "description": {"type": "string"},
                            "sku": {"type": "string"},
                            "quantity": {"type": "string"},
                            "unit_price": {"type": "string"},
                            "discount": {"type": "string"},
                            "tax": {"type": "string"},
                        },
                        "required": [
                            "description",
                            "sku",
                            "quantity",
                            "unit_price",
                            "discount",
                            "tax",
                        ],
                    },
                },
            },
            "required": [
                "supplier_name",
                "supplier_tax_id",
                "folio",
                "document_date",
                "delivered_by_name",
                "payment_method",
                "notes",
                "lines",
            ],
        },
    }

    request_body = {
        "model": settings.openrouter_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": schema,
        },
    }

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    parsed_url = urllib.parse.urlsplit(url)
    if parsed_url.scheme not in {"https", "http"} or not parsed_url.netloc:
        raise BusinessError(
            "purchase_ai_provider_unavailable",
            "La URL configurada del proveedor de IA no es válida.",
        )
    req = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://restaurantos.local",
            "X-Title": "RestaurantOS Purchase Capture",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw_payload = resp.read()
            raw_resp = json.loads(
                raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else str(raw_payload)
            )
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise BusinessError(
            "purchase_ai_upstream_error",
            (
                "No fue posible completar la lectura con el proveedor de IA. "
                "Intenta de nuevo o captura manualmente."
            ),
        ) from exc

    try:
        content = raw_resp["choices"][0]["message"]["content"]
        parsed_json = json.loads(content) if isinstance(content, str) else content
        if not isinstance(parsed_json, dict):
            raise ValueError("Invalid LLM JSON root")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise BusinessError(
            "purchase_ai_upstream_error",
            "El proveedor de IA devolvió una respuesta con formato inesperado.",
        ) from exc

    raw_lines: list[dict[str, Any]] = []
    for idx, item in enumerate(parsed_json.get("lines") or [], start=1):
        if not isinstance(item, dict):
            continue
        raw_lines.append(
            {
                "line_number": idx,
                "description": str(item.get("description") or "").strip(),
                "sku": str(item.get("sku") or "").strip(),
                "quantity": str(item.get("quantity") or "").strip(),
                "unit_price": str(item.get("unit_price") or "").strip(),
                "discount": str(item.get("discount") or "0").strip(),
                "tax": str(item.get("tax") or "0").strip(),
            }
        )

    return {
        "source_kind": "ai_vision" if b64_clean else "ai_text",
        "supplier_name": str(parsed_json.get("supplier_name") or "").strip(),
        "supplier_tax_id": str(parsed_json.get("supplier_tax_id") or "").strip().upper(),
        "folio": str(parsed_json.get("folio") or "").strip(),
        "document_date": _normalize_date(parsed_json.get("document_date")),
        "delivered_by_name": str(parsed_json.get("delivered_by_name") or "").strip(),
        "payment_method": _normalize_payment_method(parsed_json.get("payment_method")),
        "notes": str(parsed_json.get("notes") or "").strip(),
        "raw_lines": raw_lines,
        "warnings": [],
    }


def _match_supplier(
    supplier_name: str, supplier_tax_id: str, suppliers: list[dict[str, Any]]
) -> dict[str, Any] | None:
    clean_rfc = re.sub(r"[^A-Z0-9]", "", supplier_tax_id.upper())
    if clean_rfc:
        for sup in suppliers:
            sup_rfc = re.sub(r"[^A-Z0-9]", "", str(sup.get("tax_id") or "").upper())
            if sup_rfc and sup_rfc == clean_rfc:
                return sup

    if not supplier_name.strip():
        return None

    best_sup: dict[str, Any] | None = None
    best_score = 0.0
    for sup in suppliers:
        candidates = [
            str(sup.get("commercial_name") or ""),
            str(sup.get("legal_name") or ""),
            str(sup.get("code") or ""),
        ]
        score = max((_similarity(supplier_name, cand) for cand in candidates if cand), default=0.0)
        if score > best_score:
            best_score = score
            best_sup = sup

    return best_sup if best_score >= 0.65 else None


def _match_presentation(
    raw_line: dict[str, Any],
    presentations: list[dict[str, Any]],
    preferred_supplier_id: str,
) -> tuple[dict[str, Any] | None, float]:
    sku = str(raw_line.get("sku") or "").strip().lower()
    desc = str(raw_line.get("description") or "").strip()

    if sku:
        exact_sku_matches = [
            p
            for p in presentations
            if str(p.get("code") or "").strip().lower() == sku
            or str(p.get("item_sku") or "").strip().lower() == sku
        ]
        if exact_sku_matches:
            for p in exact_sku_matches:
                if preferred_supplier_id and p.get("supplier_id") == preferred_supplier_id:
                    return p, 1.0
            return exact_sku_matches[0], 0.98

    if not desc:
        return None, 0.0

    best_pres: dict[str, Any] | None = None
    best_score = 0.0
    for p in presentations:
        pres_name = str(p.get("name") or "")
        item_name = str(p.get("item_name") or "")
        code = str(p.get("code") or "")
        item_sku = str(p.get("item_sku") or "")
        candidates = [
            pres_name,
            f"{item_name} {pres_name}".strip(),
            item_name,
            code,
            item_sku,
        ]
        score = max((_similarity(desc, c) for c in candidates if c), default=0.0)
        is_preferred_supplier = (
            bool(preferred_supplier_id) and p.get("supplier_id") == preferred_supplier_id
        )
        if is_preferred_supplier and score >= 0.60:
            score = min(1.0, score + 0.05)
        if score > best_score:
            best_score = score
            best_pres = p

    if best_score >= 0.62 and best_pres is not None:
        return best_pres, round(best_score, 2)
    return None, 0.0


def _reconcile_with_branch_catalog(
    extracted: dict[str, Any],
    suppliers: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
) -> dict[str, Any]:
    matched_supplier = _match_supplier(
        extracted.get("supplier_name", ""),
        extracted.get("supplier_tax_id", ""),
        suppliers,
    )
    supplier_id = str(matched_supplier["id"]) if matched_supplier else ""
    supplier_name = (
        str(matched_supplier.get("commercial_name") or "")
        if matched_supplier
        else str(extracted.get("supplier_name") or "")
    )

    warnings: list[dict[str, Any]] = list(extracted.get("warnings") or [])
    reconciled_lines: list[dict[str, Any]] = []

    raw_lines = list(extracted.get("raw_lines") or [])[:MAX_EXTRACTED_LINES]
    for idx, raw in enumerate(raw_lines, start=1):
        line_no = int(raw.get("line_number") or idx)
        desc = str(raw.get("description") or "").strip()
        qty_dec = _parse_bounded_decimal(raw.get("quantity"), allow_zero=False)
        price_dec = _parse_bounded_decimal(raw.get("unit_price"), allow_zero=True)
        discount_dec = _parse_bounded_decimal(raw.get("discount", "0"), allow_zero=True)
        tax_dec = _parse_bounded_decimal(raw.get("tax", "0"), allow_zero=True)

        if qty_dec is None:
            warnings.append(
                {
                    "line_number": line_no,
                    "code": "invalid_or_negative_quantity",
                    "raw": desc or str(raw.get("quantity") or ""),
                }
            )
            continue
        if price_dec is None:
            warnings.append(
                {
                    "line_number": line_no,
                    "code": "invalid_or_negative_unit_price",
                    "raw": desc or str(raw.get("unit_price") or ""),
                }
            )
            continue
        if discount_dec is None or tax_dec is None:
            warnings.append(
                {
                    "line_number": line_no,
                    "code": "invalid_discount_or_tax",
                    "raw": desc,
                }
            )
            continue
        if discount_dec > qty_dec * price_dec:
            warnings.append(
                {
                    "line_number": line_no,
                    "code": "discount_exceeds_subtotal",
                    "raw": desc,
                }
            )
            continue

        matched_pres, confidence = _match_presentation(raw, presentations, supplier_id)
        if matched_pres is not None:
            pres_supplier_id = str(matched_pres.get("supplier_id") or "")
            if not supplier_id and pres_supplier_id:
                supplier_id = pres_supplier_id
                sup_obj = next((s for s in suppliers if str(s.get("id")) == supplier_id), None)
                if sup_obj:
                    supplier_name = str(sup_obj.get("commercial_name") or "")
            match_status = (
                "matched"
                if (not supplier_id or pres_supplier_id == supplier_id)
                else "cross_supplier"
            )
            reconciled_lines.append(
                {
                    "presentation_id": str(matched_pres["id"]),
                    "presentation_name": str(matched_pres.get("name") or ""),
                    "item_name": str(matched_pres.get("item_name") or ""),
                    "raw_description": desc or str(matched_pres.get("name") or ""),
                    "quantity": _format_two_decimals(qty_dec),
                    "unit_price": _format_two_decimals(price_dec),
                    "discount": _format_two_decimals(discount_dec),
                    "tax": _format_two_decimals(tax_dec),
                    "match_status": match_status,
                    "confidence": confidence,
                }
            )
        else:
            reconciled_lines.append(
                {
                    "presentation_id": "",
                    "presentation_name": "",
                    "item_name": "",
                    "raw_description": desc or "Concepto sin conciliar",
                    "quantity": _format_two_decimals(qty_dec),
                    "unit_price": _format_two_decimals(price_dec),
                    "discount": _format_two_decimals(discount_dec),
                    "tax": _format_two_decimals(tax_dec),
                    "match_status": "unmatched",
                    "confidence": 0.0,
                }
            )

    if not reconciled_lines:
        status = "insufficient_data"
    elif (
        supplier_id
        and all(line["match_status"] == "matched" for line in reconciled_lines)
        and not warnings
    ):
        status = "ready"
    else:
        status = "needs_review"

    return {
        "source_kind": extracted.get("source_kind", "text_list"),
        "status": status,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "supplier_tax_id": str(extracted.get("supplier_tax_id") or ""),
        "folio": str(extracted.get("folio") or "")[:64],
        "document_date": str(extracted.get("document_date") or ""),
        "delivered_by_name": str(extracted.get("delivered_by_name") or "")[:160],
        "payment_method": _normalize_payment_method(extracted.get("payment_method")),
        "notes": str(extracted.get("notes") or "")[:500],
        "lines": reconciled_lines,
        "warnings": warnings,
    }


def _supplier_enabled_for_branch(sup: dict[str, Any], branch_id: str) -> bool:
    if sup.get("status", "active") != "active":
        return False
    for term in sup.get("branch_terms") or ():
        if (
            isinstance(term, dict)
            and term.get("branch_id") == branch_id
            and term.get("is_enabled") is False
        ):
            return False
    return True


def extract_purchase_draft(
    session: Session, payload: dict[str, Any], actor_user_id: str | None
) -> dict[str, Any]:
    """Extract a human-reviewable purchase draft from XML, PDF, image, or shopping list text."""
    if not isinstance(payload, dict) or (set(payload) - EXTRACT_KEYS):
        raise BusinessError(
            "purchase_extract_payload_invalid",
            "La solicitud de extracción contiene campos no permitidos.",
        )

    branch_id_raw = payload.get("branch_id")
    if not isinstance(branch_id_raw, str) or not branch_id_raw.strip():
        raise BusinessError(
            "purchase_extract_payload_invalid",
            "branch_id es obligatorio para extraer un documento de compra.",
        )
    branch_id = branch_id_raw.strip()

    authorize_branch_scope(session, _actor_user_id(actor_user_id), "purchases.manage", branch_id)

    raw_text_val = payload.get("raw_text")
    if raw_text_val is not None and not isinstance(raw_text_val, str):
        raise BusinessError("purchase_extract_payload_invalid", "raw_text debe ser texto.")
    raw_text = (raw_text_val or "").strip()
    if len(raw_text) > MAX_RAW_TEXT_CHARS:
        raise BusinessError(
            "purchase_extract_size_exceeded",
            f"El texto excede el máximo de {MAX_RAW_TEXT_CHARS} caracteres.",
        )

    file_b64_val = payload.get("file_base64")
    if file_b64_val is not None and not isinstance(file_b64_val, str):
        raise BusinessError("purchase_extract_payload_invalid", "file_base64 debe ser texto.")
    file_base64 = (file_b64_val or "").strip()
    mime_type = str(payload.get("mime_type") or "").strip()
    filename = str(payload.get("filename") or "").strip()

    all_suppliers = list_suppliers(session)
    branch_suppliers = [
        sup for sup in all_suppliers if _supplier_enabled_for_branch(sup, branch_id)
    ]
    presentations = [
        pres
        for pres in list_purchase_presentations(session, branch_id=branch_id)
        if pres.get("status", "active") == "active"
    ]

    if not file_base64 and not raw_text:
        return {
            "source_kind": "text_list",
            "status": "insufficient_data",
            "supplier_id": "",
            "supplier_name": "",
            "supplier_tax_id": "",
            "folio": "",
            "document_date": "",
            "delivered_by_name": "",
            "payment_method": "cash",
            "notes": "",
            "lines": [],
            "warnings": [{"line_number": 0, "code": "empty_input", "raw": ""}],
        }

    if file_base64:
        raw_bytes, validated_mime, clean_b64 = _detect_and_validate_file(
            file_base64, mime_type, filename
        )
        if validated_mime == "application/xml":
            extracted = _extract_from_cfdi_xml(raw_bytes)
        elif validated_mime == "application/pdf":
            pdf_text = _extract_text_from_pdf_bytes(raw_bytes)
            combined_text = f"{pdf_text}\n{raw_text}".strip() if raw_text else pdf_text
            parsed_pdf = (
                _parse_structured_or_natural_text(combined_text)
                if combined_text
                else {"raw_lines": []}
            )
            if parsed_pdf.get("raw_lines"):
                parsed_pdf["source_kind"] = "pdf_text"
                extracted = parsed_pdf
            else:
                extracted = _call_openrouter_extraction(
                    b64_clean=clean_b64,
                    mime_type=validated_mime,
                    filename=filename or "documento.pdf",
                    raw_text=combined_text,
                    suppliers=branch_suppliers,
                    presentations=presentations,
                )
        else:
            extracted = _call_openrouter_extraction(
                b64_clean=clean_b64,
                mime_type=validated_mime,
                filename=filename or "imagen",
                raw_text=raw_text,
                suppliers=branch_suppliers,
                presentations=presentations,
            )
    else:
        extracted = _parse_structured_or_natural_text(raw_text)
        if not extracted.get("raw_lines") and (get_settings().openrouter_api_key or "").strip():
            extracted = _call_openrouter_extraction(
                b64_clean=None,
                mime_type=None,
                filename="",
                raw_text=raw_text,
                suppliers=branch_suppliers,
                presentations=presentations,
            )

    return _reconcile_with_branch_catalog(extracted, branch_suppliers, presentations)

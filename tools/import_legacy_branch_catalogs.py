#!/usr/bin/env python3
"""Validate and upload legacy branch workbooks without committing their data.

The source files are Office Open XML workbooks even when their extension is
`.XLS`. This adapter intentionally uses only the Python standard library so it
can run from an operator workstation without adding a production dependency.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

SOURCES = {
    "CLIENTES.XLS": "customer",
    "INSUMOS.XLS": "inventory_item",
    "PRESENTACIONES.XLS": "presentation",
    "PRODUCTOS.XLS": "product",
    "RECETAS.XLS": "recipe",
}
CELL_REFERENCE = re.compile(r"([A-Z]+)")
LEADING_IMPORT_QUOTES = "'´‘’"


def _identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if character.isalnum()).casefold()


def _column_index(reference: str) -> int:
    match = CELL_REFERENCE.match(reference)
    if not match:
        return 0
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root:
        values.append("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")))
    return values


def workbook_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[list[str]] = []
    for row_node in (node for node in root.iter() if node.tag.endswith("}row")):
        cells: dict[int, str] = {}
        for cell in (node for node in row_node if node.tag.endswith("}c")):
            index = _column_index(cell.attrib.get("r", "A1"))
            cell_type = cell.attrib.get("t")
            value_node = next((node for node in cell if node.tag.endswith("}v")), None)
            if cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
            else:
                value = value_node.text if value_node is not None and value_node.text else ""
                if cell_type == "s" and value:
                    value = shared[int(value)]
            cells[index] = value.strip()
        width = max(cells, default=-1) + 1
        rows.append([cells.get(index, "") for index in range(width)])
    if len(rows) < 5:
        raise ValueError(f"{path.name}: no contiene la fila de encabezados esperada")
    headers = [value.strip().upper() for value in rows[4]]
    result = []
    for values in rows[5:]:
        padded = values + [""] * (len(headers) - len(values))
        record = {headers[index]: padded[index] for index in range(len(headers))}
        if any(record.values()):
            result.append(record)
    return result


def _cents(value: str) -> int:
    try:
        return int((Decimal(value or "0") * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError("precio no numérico") from exc


def _product_sku(value: str) -> str:
    return value.strip().lstrip(LEADING_IMPORT_QUOTES).strip()


def normalize(entity_type: str, row: dict[str, str]) -> dict[str, Any]:
    if entity_type == "customer":
        return {"name": row.get("NOMBRE", ""), "legacy_address": row.get("DIRECCION", "")}
    if entity_type == "inventory_item":
        return {
            "sku": row.get("CLAVE", ""),
            "name": row.get("DESCRIPCION", ""),
            "category_name": row.get("GRUPODEINSUMOS", "") or row.get("GRUPO", ""),
            "unit_code": row.get("UNIDADDEMEDIDA", ""),
            "legacy_last_cost": row.get("ULTIMOCOSTO", ""),
            "legacy_average_cost": row.get("COSTOPROMEDIO", ""),
            "tax_rate": row.get("IMPUESTO", ""),
        }
    if entity_type == "product":
        return {
            "sku": _product_sku(row.get("CLAVE", "")),
            "name": row.get("DESCRIPCION", ""),
            "category_name": row.get("GRUPODEPRODUCTOS", ""),
            "price_cents": _cents(row.get("PRECIO", "")),
            "pre_tax_price": row.get("PRECIOSINIMPUESTOS", ""),
            "tax_amount": row.get("IMPUESTOS", ""),
            "legacy_channels": {
                "comedor": row.get("COMEDOR", ""),
                "domicilio": row.get("DOMICILIO", ""),
                "rapido": row.get("RAPIDO", ""),
            },
        }
    if entity_type == "presentation":
        return {
            "sku": row.get("CLAVE", ""),
            "name": row.get("DESCRIPCION", ""),
            "category_name": row.get("GRUPODEINSUMOS", "") or row.get("GRUPO", ""),
            "yield": row.get("RENDIMIENTO", ""),
            "unit_code": row.get("UNIDAD", ""),
            "legacy_last_cost": row.get("ULTIMOCOSTO", ""),
            "legacy_average_cost": row.get("COSTOPROMEDIO", ""),
            "tax_rate": row.get("IMPUESTO", ""),
            "supplier_code": "",
        }
    return {
        "sku": row.get("CLAVE", ""),
        "name": row.get("DESCRIPCION", ""),
        "components": [],
        "source_columns": sorted(row),
    }


def manifest_for(directory: Path) -> tuple[dict[str, Any], str]:
    files = []
    for filename, entity_type in SOURCES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Falta {filename}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = workbook_rows(path)
        files.append(
            {"filename": filename, "entity_type": entity_type, "sha256": digest, "rows": len(rows)}
        )
    manifest = {"format": "restaurantos-legacy-import-v1", "files": files}
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return manifest, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def iter_records(directory: Path) -> Iterator[dict[str, Any]]:
    for filename, entity_type in SOURCES.items():
        rows = workbook_rows(directory / filename)
        seen: Counter[str] = Counter()
        for row_number, row in enumerate(rows, start=6):
            base_key = row.get("CLAVE", "").strip() or f"row-{row_number}"
            seen[base_key] += 1
            source_key = base_key if seen[base_key] == 1 else f"{base_key}#row-{row_number}"
            yield {
                "entity_type": entity_type,
                "source_key": source_key,
                "source_row": row_number,
                "raw_payload": row,
                "normalized_payload": normalize(entity_type, row),
            }


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.token = token

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")[:1000]
            raise RuntimeError(f"API {exc.code} en {path}: {detail}") from exc


def upload(args: argparse.Namespace, manifest: dict[str, Any], checksum: str) -> None:
    token = os.environ.get(args.token_env, "").strip()
    client = ApiClient(args.api_url, token or None)
    if not token:
        email = os.environ.get(args.email_env, "").strip()
        if not email:
            raise RuntimeError(f"Define {args.email_env} con el correo del administrador")
        password = getpass.getpass("Contraseña del administrador (no se mostrará): ")
        response = client.request("POST", "/auth/login", {"email": email, "password": password})
        client.token = str(response["token"])

    branch_id = args.branch_id
    if not branch_id:
        branches = client.request("GET", "/branches")
        requested_branch = _identity(args.branch)
        matches = [
            branch
            for branch in branches
            if _identity(str(branch.get("code", ""))) == requested_branch
            or _identity(str(branch.get("name", ""))) == requested_branch
        ]
        if len(matches) != 1:
            raise RuntimeError("No se encontró una única sucursal Constitución; usa --branch-id")
        branch_id = str(matches[0]["id"])

    batch = client.request(
        "POST",
        "/legacy-imports",
        {
            "branch_id": branch_id,
            "source_system": args.source_system,
            "manifest_checksum": checksum,
            "manifest": manifest,
        },
    )
    batch_id = str(batch["id"])
    pending: list[dict[str, Any]] = []
    uploaded = Counter()
    for record in iter_records(args.directory):
        pending.append(record)
        if len(pending) == args.chunk_size:
            response = client.request(
                "POST", f"/legacy-imports/{batch_id}/records", {"records": pending}
            )
            uploaded.update(response.get("counts", {}))
            pending = []
    if pending:
        response = client.request(
            "POST", f"/legacy-imports/{batch_id}/records", {"records": pending}
        )
        uploaded.update(response.get("counts", {}))
    completed = client.request("POST", f"/legacy-imports/{batch_id}/complete", {})
    print(
        json.dumps(
            {"batch_id": batch_id, "uploaded": uploaded, "summary": completed["summary"]},
            ensure_ascii=False,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Carpeta privada que contiene los cinco Excel")
    parser.add_argument(
        "--apply", action="store_true", help="Carga los datos; sin esta opción sólo valida"
    )
    parser.add_argument("--api-url", default="", help="URL HTTPS del despliegue, sin /api/v1")
    parser.add_argument(
        "--branch", default="Constitución", help="Código o nombre exacto de sucursal"
    )
    parser.add_argument(
        "--branch-id", default="", help="ID canónico, si no se desea resolver por nombre"
    )
    parser.add_argument(
        "--source-system", default="softrestaurant", help="Identificador del origen"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=250, choices=range(1, 501), metavar="1..500"
    )
    parser.add_argument("--token-env", default="RESTAURANTOS_IMPORT_TOKEN")
    parser.add_argument("--email-env", default="RESTAURANTOS_IMPORT_EMAIL")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest, checksum = manifest_for(args.directory)
        counts = {item["entity_type"]: item["rows"] for item in manifest["files"]}
        print(
            json.dumps(
                {"validation": "ok", "manifest_checksum": checksum, "counts": counts},
                ensure_ascii=False,
            )
        )
        if args.apply:
            if not args.api_url.startswith("https://") and not args.api_url.startswith(
                "http://localhost"
            ):
                raise RuntimeError("--api-url debe usar HTTPS, salvo localhost")
            upload(args, manifest, checksum)
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

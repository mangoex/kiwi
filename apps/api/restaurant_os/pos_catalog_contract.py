"""Small dependency-free validator for the versioned public POS catalog schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "schemas"
    / "pos-catalog-projection-v1.schema.json"
)


def validate_pos_catalog_projection(payload: dict[str, Any]) -> None:
    """Raise ValueError when a public POS projection violates its versioned JSON Schema."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    _validate(schema, payload, schema, "$")


def _validate(schema: dict[str, Any], value: Any, root: dict[str, Any], path: str) -> None:
    if "$ref" in schema:
        reference = str(schema["$ref"])
        if not reference.startswith("#/$defs/"):
            raise ValueError(f"{path}: referencia de schema no soportada")
        _validate(root["$defs"][reference.rsplit("/", 1)[-1]], value, root, path)
        return
    if "oneOf" in schema:
        errors: list[str] = []
        for candidate in schema["oneOf"]:
            try:
                _validate(candidate, value, root, path)
                return
            except ValueError as exc:
                errors.append(str(exc))
        raise ValueError(f"{path}: no coincide con ninguna variante ({'; '.join(errors)})")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path}: debe ser {schema['const']!r}")
    expected_types = schema.get("type")
    if expected_types is not None:
        candidates = expected_types if isinstance(expected_types, list) else [expected_types]
        if not any(_matches_type(value, candidate) for candidate in candidates):
            raise ValueError(f"{path}: tipo inválido, se esperaba {expected_types}")
    if "minimum" in schema and isinstance(value, int) and value < schema["minimum"]:
        raise ValueError(f"{path}: debe ser mayor o igual a {schema['minimum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}.{key}: es obligatorio")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(properties)
            if extras:
                raise ValueError(f"{path}: propiedades adicionales no permitidas: {sorted(extras)}")
        for key, child in properties.items():
            if key in value:
                _validate(child, value[key], root, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate(schema["items"], item, root, f"{path}[{index}]")


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    raise ValueError(f"Tipo de schema no soportado: {expected}")

from __future__ import annotations

import json
from pathlib import Path


def test_admin_product_configuration_schema_is_strict() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / "packages/contracts/schemas/admin-product-configuration-v1.schema.json").read_text()
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "name",
        "sku",
        "category_id",
        "subgroup_option_value_id",
        "price_cents",
        "station",
        "image_url",
        "status",
    }
    assert schema["properties"]["station"]["enum"] == ["kitchen", "drinks", "packing"]
    assert "tax_rate" not in schema["properties"]

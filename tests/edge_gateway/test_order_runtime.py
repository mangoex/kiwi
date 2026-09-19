import json

import pytest
from edge_gateway.order_runtime import load_order_runtime_paths


def test_order_runtime_paths_are_opt_in_and_isolated(tmp_path):
    config = tmp_path / "gateway.json"
    config.write_text("{}")
    assert load_order_runtime_paths(config, tmp_path) is None
    data = {
        "orders": {
            "database": str(tmp_path / "orders.db"),
            "catalog_database": str(tmp_path / "catalog.db"),
            "bundle": str(tmp_path / "bundle.json"),
            "signing_key": str(tmp_path / "key.pem"),
        }
    }
    for name in ("bundle.json", "key.pem"):
        (tmp_path / name).write_text("synthetic")
    config.write_text(json.dumps(data))
    result = load_order_runtime_paths(config, tmp_path)
    assert result.database == tmp_path / "orders.db"
    data["orders"]["database"] = str(tmp_path.parent / "outside.db")
    config.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_order_runtime_paths(config, tmp_path)


def test_order_runtime_rejects_aliasing_files(tmp_path):
    config = tmp_path / "gateway.json"
    file = tmp_path / "existing"
    file.write_text("synthetic")
    config.write_text(
        json.dumps(
            {
                "orders": dict.fromkeys(
                    ("database", "catalog_database", "bundle", "signing_key"), str(file)
                )
            }
        )
    )
    with pytest.raises(ValueError):
        load_order_runtime_paths(config, tmp_path)

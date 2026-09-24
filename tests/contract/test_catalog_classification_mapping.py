"""Mapping preparation cannot infer classification or vary idempotency during retry."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "classification_mapping",
    Path(__file__).resolve().parents[2] / "scripts/classification_mapping.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_mapping_is_explicit_repeatable_and_stale_versions_are_kept():
    rows = [
        {
            "id": "group-1",
            "classification_code": "food",
            "configuration_version": 3,
            "status": "active",
        }
    ]
    commands = module.mapping_commands(rows)
    assert commands == module.mapping_commands(rows)
    assert commands[0]["payload"] == {"classification_code": "food", "expected_version": 3}
    with pytest.raises(ValueError):
        module.mapping_commands([{**rows[0], "classification_code": None}])
    with pytest.raises(ValueError):
        module.mapping_commands(rows + rows)
    assert (
        module.NoRedirect().redirect_request(None, None, 302, "", {}, "https://foreign.invalid")
        is None
    )

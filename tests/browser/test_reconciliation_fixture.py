"""Fixture cloning stays in OS temp or the explicitly configured CI task temp."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "reconciliation_fixture", Path(__file__).with_name("seed_reconciliation_fixture.py")
)
assert spec and spec.loader
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.mark.parametrize("location", ["os", "runner", "outside"])
def test_manifest_is_confined_to_task_temporary_roots(tmp_path, monkeypatch, location):
    os_temp = tmp_path / "os"
    runner_temp = tmp_path / "runner"
    monkeypatch.setattr(fixture.tempfile, "gettempdir", lambda: str(os_temp))
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    manifest = tmp_path / location / "manifest.json"
    if location == "outside":
        with pytest.raises(RuntimeError, match="task temporary directory"):
            fixture.fixture_manifest_path(manifest)
    else:
        assert fixture.fixture_manifest_path(manifest) == manifest.resolve()

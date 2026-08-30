"""Regression tests for canonical SPA static-root containment."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from restaurant_os.main import create_app


def _static_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Path]:
    static_root = tmp_path / "static"
    for app_name, marker in (("admin-web", "ADMIN_ROOT"), ("pos-web", "POS_ROOT")):
        app_root = static_root / app_name
        app_root.mkdir(parents=True)
        (app_root / "index.html").write_text(marker, encoding="utf-8")
    (static_root / "admin-web" / "asset.txt").write_text("ADMIN_ASSET", encoding="utf-8")
    monkeypatch.setenv("STATIC_DIR", str(static_root))
    return TestClient(create_app()), static_root


def test_encoded_parent_path_cannot_cross_spa_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _ = _static_client(monkeypatch, tmp_path)

    escaped = client.get("/admin/%2e%2e/pos-web/index.html")
    assert escaped.status_code == 404
    assert "POS_ROOT" not in escaped.text

    assert client.get("/admin/asset.txt").text == "ADMIN_ASSET"
    assert client.get("/admin/an/internal/route").text == "ADMIN_ROOT"


def test_symlink_cannot_escape_spa_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, static_root = _static_client(monkeypatch, tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_SECRET", encoding="utf-8")
    link = static_root / "admin-web" / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    escaped = client.get("/admin/linked.txt")
    assert escaped.status_code == 404
    assert "OUTSIDE_SECRET" not in escaped.text

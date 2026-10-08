"""Tests for product image upload and static serving."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from test_platform_api import (
    _admin_headers,
    _client_with_seeded_database,
)


def test_product_image_upload_requires_authentication() -> None:
    client = _client_with_seeded_database()
    file_content = b"\x89PNG\r\n\x1a\nfake-png-content"
    response = client.post(
        "/api/v1/catalog/products/upload-image",
        files={"file": ("test.png", io.BytesIO(file_content), "image/png")},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "actor_required"


def test_product_image_upload_rejects_invalid_extension() -> None:
    client = _client_with_seeded_database()
    headers = _admin_headers()
    file_content = b"not-an-image"
    response = client.post(
        "/api/v1/catalog/products/upload-image",
        headers=headers,
        files={"file": ("malicious.exe", io.BytesIO(file_content), "application/x-msdownload")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_image_format"


def test_product_image_upload_rejects_empty_file() -> None:
    client = _client_with_seeded_database()
    headers = _admin_headers()
    response = client.post(
        "/api/v1/catalog/products/upload-image",
        headers=headers,
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_file"


def test_product_image_upload_rejects_oversized_file() -> None:
    client = _client_with_seeded_database()
    headers = _admin_headers()
    oversized = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/catalog/products/upload-image",
        headers=headers,
        files={"file": ("large.png", io.BytesIO(oversized), "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "image_too_large"


def test_product_image_upload_and_serving_success(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    client = _client_with_seeded_database()
    headers = _admin_headers()
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtestvalid"
    response = client.post(
        "/api/v1/catalog/products/upload-image",
        headers=headers,
        files={"file": ("tacos.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "image_url" in data
    assert data["image_url"].startswith("/uploads/products/")
    assert data["image_url"].endswith(".png")
    assert data["size_bytes"] == len(png_bytes)

    # Test serving via GET /uploads/products/...
    serve_res = client.get(data["image_url"])
    assert serve_res.status_code == 200
    assert serve_res.content == png_bytes

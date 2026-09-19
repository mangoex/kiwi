"""Durability barriers for publishing order catalog lifecycle artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import edge_gateway.order_lifecycle as lifecycle
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway.order_outbox import OrderOutbox
from restaurant_os.offline_orders import sign_bundle


def _bundle(key: Ed25519PrivateKey, *, bundle_id: str) -> dict[str, Any]:
    return sign_bundle(
        {
            "manifest": {
                "schema_version": "ord-off/v1",
                "organization_id": "org",
                "branch_id": "branch",
                "device_id": "device",
                "bundle_id": bundle_id,
                "lease_epoch": 1,
                "issued_at": 1,
                "expires_at": 7_201,
            },
            "catalog": {},
            "operational_seed": {},
        },
        key,
        kid="central",
    )


def test_catalog_file_is_fsynced_after_sqlite_dispose_before_rename(
    tmp_path: Path, monkeypatch
) -> None:
    destination = tmp_path / "catalog.db"
    destination.write_bytes(b"prior-catalog")
    events: list[str] = []

    class _CatalogEngine:
        def dispose(self) -> None:
            events.append("disposed")

    class _Snapshot:
        def close(self) -> None:
            events.append("snapshot_closed")

    monkeypatch.setattr(lifecycle.sa, "create_engine", lambda _url: _CatalogEngine())
    import restaurant_os.offline_order_catalog as catalog

    monkeypatch.setattr(catalog, "hydrate_catalog_snapshot", lambda *_args, **_kwargs: _Snapshot())
    monkeypatch.setattr(lifecycle, "_fsync_file", lambda _path: events.append("file_fsynced"))
    monkeypatch.setattr(
        lifecycle, "_fsync_directory", lambda _path: events.append("directory_fsynced")
    )

    lifecycle._replace_catalog_database(
        destination,
        {"manifest": {}, "catalog": {}, "operational_seed": {}},
    )

    assert events == ["snapshot_closed", "disposed", "file_fsynced", "directory_fsynced"]


def test_failed_directory_fsync_leaves_refresh_journal_for_safe_resume(
    tmp_path: Path, monkeypatch
) -> None:
    signing_key = Ed25519PrivateKey.generate()
    current = _bundle(signing_key, bundle_id=str(uuid4()))
    candidate = _bundle(signing_key, bundle_id=str(uuid4()))
    bundle_path = tmp_path / "bundle.json"
    catalog_path = tmp_path / "catalog.db"
    bundle_path.write_text(json.dumps(current), encoding="utf-8")
    outbox = OrderOutbox(tmp_path / "orders.db")
    outbox.ensure_active_bundle(current["hash"], 1)
    monkeypatch.setattr(lifecycle, "refresh_catalog_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lifecycle, "_replace_catalog_database", lambda *_args, **_kwargs: None)
    original_directory_fsync = lifecycle._fsync_directory
    monkeypatch.setattr(
        lifecycle,
        "_fsync_directory",
        lambda _path: (_ for _ in ()).throw(OSError("injected directory fsync failure")),
    )
    try:
        try:
            lifecycle.renew_gateway_catalog(
                outbox,
                catalog_database=catalog_path,
                bundle_path=bundle_path,
                keyring={"central": signing_key.public_key()},
                request_bundle=lambda: candidate,
            )
        except OSError as error:
            assert "injected directory fsync failure" in str(error)
        else:
            raise AssertionError("directory fsync failure did not stop publication")
        assert outbox.lifecycle_status() == "REFRESHING"

        monkeypatch.setattr(lifecycle, "_fsync_directory", original_directory_fsync)
        resumed = lifecycle.recover_catalog_refresh(
            outbox,
            catalog_database=catalog_path,
            bundle_path=bundle_path,
            keyring={"central": signing_key.public_key()},
        )
        assert resumed is not None and resumed["hash"] == candidate["hash"]
        assert outbox.lifecycle_status() == "ACTIVE"
        assert outbox.active_bundle_matches(candidate["hash"], 1)
    finally:
        outbox.engine.dispose()

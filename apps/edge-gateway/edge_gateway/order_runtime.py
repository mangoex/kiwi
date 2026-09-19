"""Opt-in order storage paths; cash-only installations keep their configuration."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from edge_gateway.config import (
    _absolute_readable_path,
    _absolute_writable_path,
    _require_distinct_paths,
    load_gateway_credential,
    load_public_keyring,
    load_runtime_config,
)


@dataclass(frozen=True)
class OrderRuntimePaths:
    database: Path
    catalog_database: Path
    bundle: Path
    signing_key: Path


def load_order_runtime_paths(
    config_path: Path, runtime_root: Path, *, allow_missing_bundle: bool = False
) -> OrderRuntimePaths | None:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if "orders" not in raw:
        return None
    options = raw["orders"]
    fields = {"database", "catalog_database", "bundle", "signing_key"}
    if not isinstance(options, dict) or set(options) != fields:
        raise ValueError("gateway order configuration fields are invalid")
    if any(not isinstance(options[name], str) or not options[name] for name in fields):
        raise ValueError("gateway order paths are invalid")
    bundle_path = (
        _absolute_writable_path(options["bundle"], "bundle", runtime_root)
        if allow_missing_bundle
        else _absolute_readable_path(options["bundle"], "bundle", runtime_root)
    )
    paths = OrderRuntimePaths(
        database=_absolute_writable_path(options["database"], "orders", runtime_root),
        catalog_database=_absolute_writable_path(
            options["catalog_database"], "catalog", runtime_root
        ),
        bundle=bundle_path,
        signing_key=_absolute_readable_path(options["signing_key"], "signing key", runtime_root),
    )
    protected = [
        config_path,
        paths.database,
        paths.catalog_database,
        paths.bundle,
        paths.signing_key,
    ]
    protected.extend(
        Path(raw[name])
        for name in ("sqlite_path", "public_keyring_path", "credential_path", "log_path")
        if name in raw
    )
    _require_distinct_paths(tuple(protected))
    return paths


class _OrderBootstrapTransport:
    """Closed HTTPS transport for the two initial order bootstrap calls."""

    def __init__(
        self,
        central_url: str,
        credential: str,
        *,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self._client = client_factory(
            base_url=central_url.rstrip("/"),
            timeout=httpx.Timeout(5.0),
            verify=True,
            trust_env=False,
            follow_redirects=False,
            headers={"X-Device-Token": credential},
        )

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise ValueError("offline_order_bootstrap_transport_failed") from exc
        if response.status_code != 200:
            raise ValueError("offline_order_bootstrap_http_failed")
        try:
            body = response.json()
        except ValueError as exc:
            raise ValueError("offline_order_bootstrap_response_invalid") from exc
        if not isinstance(body, dict):
            raise ValueError("offline_order_bootstrap_response_invalid")
        return body

    def close(self) -> None:
        self._client.close()


def handoff_orders(
    config_path: str | Path,
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> dict[str, Any]:
    """Durably freeze and return branch order authority to the central service."""
    config, paths, bundle, keyring, private_key, outbox = _open_order_lifecycle(config_path)
    try:
        # The durable order gate comes first.  A failed cash reconciliation
        # therefore cannot leave a window in which a new order arrives after
        # the operator initiated the authority return.
        outbox.begin_freeze(
            handoff_id=str(uuid4()),
            organization_id=config.organization_id,
            branch_id=config.branch_id,
            device_id=config.source_device_id,
            lease_epoch=int(bundle["manifest"]["lease_epoch"]),
        )
        if _cash_reconciliation_pending(config.sqlite_path):
            raise ValueError("offline_handoff_cash_reconciliation_incomplete")
        from edge_gateway.order_lifecycle import handoff_gateway

        transport = _OrderBootstrapTransport(
            config.central_url,
            load_gateway_credential(config.credential_path, runtime_root=config.runtime_root),
            client_factory=client_factory,
        )
        try:
            receipt = handoff_gateway(
                outbox,
                organization_id=config.organization_id,
                branch_id=config.branch_id,
                device_id=config.source_device_id,
                lease_epoch=int(bundle["manifest"]["lease_epoch"]),
                private_key=private_key,
                send=lambda payload: transport.post("/api/v1/offline-orders/handoff", payload),
            )
        finally:
            transport.close()
        return _handoff_result(receipt)
    finally:
        outbox.engine.dispose()


def renew_orders(
    config_path: str | Path,
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> dict[str, Any]:
    """Install a newly signed catalog for the current, unchanged lease epoch."""
    config, paths, bundle, keyring, _private_key, outbox = _open_order_lifecycle(config_path)
    try:
        from edge_gateway.order_lifecycle import renew_gateway_catalog

        public_key = _device_public_key(paths.signing_key, config.runtime_root)
        epoch = int(bundle["manifest"]["lease_epoch"])
        transport = _OrderBootstrapTransport(
            config.central_url,
            load_gateway_credential(config.credential_path, runtime_root=config.runtime_root),
            client_factory=client_factory,
        )
        try:
            refreshed = renew_gateway_catalog(
                outbox,
                catalog_database=paths.catalog_database,
                bundle_path=paths.bundle,
                keyring=keyring,
                request_bundle=lambda: transport.post(
                    "/api/v1/offline-orders/catalog-renew",
                    {"lease_epoch": epoch, "public_key": public_key},
                ),
            )
        finally:
            transport.close()
        return {
            "status": "renewed",
            "bundle_hash": str(refreshed["hash"]),
            "lease_epoch": int(refreshed["manifest"]["lease_epoch"]),
        }
    finally:
        outbox.engine.dispose()


def recover_orders(
    config_path: str | Path,
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> dict[str, Any]:
    """Explicitly recover a released gateway into the next lease epoch."""
    config, paths, bundle, keyring, _private_key, outbox = _open_order_lifecycle(config_path)
    try:
        from edge_gateway.order_lifecycle import recover_gateway_catalog

        try:
            previous_manifest = outbox.handoff_payload()["manifest"]
        except ValueError as exc:
            raise ValueError("offline_recovery_handoff_required") from exc
        handoff_id = previous_manifest.get("handoff_id")
        previous_epoch = previous_manifest.get("lease_epoch")
        if not isinstance(handoff_id, str) or not isinstance(previous_epoch, int):
            raise ValueError("offline_recovery_handoff_required")
        public_key = _device_public_key(paths.signing_key, config.runtime_root)
        transport = _OrderBootstrapTransport(
            config.central_url,
            load_gateway_credential(config.credential_path, runtime_root=config.runtime_root),
            client_factory=client_factory,
        )
        try:
            recovered = transport.post(
                "/api/v1/offline-orders/recover-lease",
                {"handoff_id": handoff_id, "public_key": public_key},
            )
            epoch = recovered.get("lease_epoch")
            if (
                recovered.get("branch_id") != config.branch_id
                or recovered.get("status") != "active"
                or isinstance(epoch, bool)
                or not isinstance(epoch, int)
                or epoch != previous_epoch + 1
            ):
                raise ValueError("offline_recovery_response_invalid")
            downloaded = transport.post(
                "/api/v1/offline-orders/bootstrap",
                {"lease_epoch": epoch, "public_key": public_key},
            )
        finally:
            transport.close()
        verified = _verify_bootstrap_bundle(downloaded, keyring, config, epoch)
        refreshed = recover_gateway_catalog(
            outbox,
            catalog_database=paths.catalog_database,
            bundle_path=paths.bundle,
            keyring=keyring,
            bundle=verified,
            handoff_id=handoff_id,
            expected_previous_epoch=previous_epoch,
        )
        return {
            "status": "recovered",
            "bundle_hash": str(refreshed["hash"]),
            "lease_epoch": int(refreshed["manifest"]["lease_epoch"]),
        }
    finally:
        outbox.engine.dispose()


def orders_status(config_path: str | Path) -> dict[str, Any]:
    """Read the gateway order authority state without exposing credentials."""
    config = load_runtime_config(config_path, allow_missing_order_bundle=True)
    paths = load_order_runtime_paths(
        Path(config_path), config.runtime_root, allow_missing_bundle=True
    )
    if paths is None:
        raise ValueError("offline_order_bootstrap_not_configured")
    keyring = load_public_keyring(config.public_keyring_path)
    bundle = _existing_bundle(paths.bundle, keyring, config)
    if bundle is None or not paths.database.exists():
        return {"ready": False, "lifecycle": "unprepared"}
    from edge_gateway.order_outbox import OrderOutbox

    outbox = OrderOutbox(paths.database)
    try:
        lifecycle = outbox.lifecycle_status()
        active = lifecycle == "ACTIVE" and outbox.active_bundle_matches(
            str(bundle["hash"]), int(bundle["manifest"]["lease_epoch"])
        )
        return {
            "ready": active,
            "lifecycle": lifecycle.lower(),
            "bundle_hash": str(bundle["hash"]),
            "lease_epoch": int(bundle["manifest"]["lease_epoch"]),
        }
    finally:
        outbox.engine.dispose()


def _open_order_lifecycle(
    config_path: str | Path,
) -> tuple[Any, OrderRuntimePaths, dict[str, Any], dict[str, Any], Any, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from edge_gateway.order_outbox import OrderOutbox

    config = load_runtime_config(config_path)
    paths = load_order_runtime_paths(Path(config_path), config.runtime_root)
    if paths is None:
        raise ValueError("offline_order_bootstrap_not_configured")
    keyring = load_public_keyring(config.public_keyring_path)
    bundle = _existing_bundle(paths.bundle, keyring, config)
    if bundle is None:
        raise ValueError("offline_order_bundle_missing")
    try:
        private_key = serialization.load_pem_private_key(
            load_gateway_credential(paths.signing_key, runtime_root=config.runtime_root).encode(),
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("offline_order_device_key_invalid") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("offline_order_device_key_invalid")
    return config, paths, bundle, keyring, private_key, OrderOutbox(paths.database)


def _cash_reconciliation_pending(path: Path) -> bool:
    """Return whether the independent cash protocol has terminally reconciled."""
    if not path.exists():
        return False
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("cash_database_invalid")
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as connection:
            if not _table_exists(connection, "local_commands"):
                return False
            pending = connection.execute(
                "SELECT 1 FROM local_commands "
                "WHERE command_type = ? AND status != 'CONFIRMED' LIMIT 1",
                ("cash.movement.create.v1",),
            ).fetchone()
    except sqlite3.Error as exc:
        raise ValueError("cash_reconciliation_inspection_failed") from exc
    return pending is not None


def _handoff_result(receipt: dict[str, Any]) -> dict[str, Any]:
    fields = ("handoff_id", "branch_id", "lease_epoch", "watermark", "manifest_hash")
    if receipt.get("status") != "released" or any(field not in receipt for field in fields):
        raise ValueError("offline_handoff_response_invalid")
    return {"status": "released", **{field: receipt[field] for field in fields}}


def prepare_orders(
    config_path: str | Path,
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> dict[str, Any]:
    """Fetch and atomically install the first verified branch order bundle only."""
    config = load_runtime_config(config_path, allow_missing_order_bundle=True)
    paths = load_order_runtime_paths(
        Path(config_path), config.runtime_root, allow_missing_bundle=True
    )
    if paths is None:  # ``orders`` is mandatory for this explicit subcommand.
        raise ValueError("offline_order_bootstrap_not_configured")
    keyring = load_public_keyring(config.public_keyring_path)
    public_key = _device_public_key(paths.signing_key, config.runtime_root)

    existing = _existing_bundle(paths.bundle, keyring, config)
    if existing is not None:
        return {
            "status": "already_prepared",
            "bundle_hash": existing["hash"],
            "lease_epoch": existing["manifest"]["lease_epoch"],
        }
    if _operational_order_data_exists(paths.database):
        raise ValueError("order_bundle_refresh_requires_protocol")
    if _installed_bundle_hash(paths.database) or _installed_bundle_hash(paths.catalog_database):
        raise ValueError("order_bundle_refresh_requires_protocol")

    transport = _OrderBootstrapTransport(
        config.central_url,
        load_gateway_credential(config.credential_path, runtime_root=config.runtime_root),
        client_factory=client_factory,
    )
    try:
        lease = transport.post("/api/v1/offline-orders/lease", {"public_key": public_key})
        epoch = lease.get("lease_epoch")
        if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1:
            raise ValueError("offline_order_bootstrap_response_invalid")
        downloaded = transport.post(
            "/api/v1/offline-orders/bootstrap",
            {"lease_epoch": epoch, "public_key": public_key},
        )
    finally:
        transport.close()

    verified = _verify_bootstrap_bundle(downloaded, keyring, config, epoch)
    _write_new_bundle(paths.bundle, verified)
    return {"status": "prepared", "bundle_hash": verified["hash"], "lease_epoch": epoch}


def _device_public_key(path: Path, runtime_root: Path) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    try:
        private_key = serialization.load_pem_private_key(
            load_gateway_credential(path, runtime_root=runtime_root).encode("utf-8"), password=None
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("offline_order_device_key_invalid") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("offline_order_device_key_invalid")
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return public_key.decode("ascii")


def _existing_bundle(path: Path, keyring: dict[str, Any], config: Any) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("offline_order_bundle_target_invalid")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        from restaurant_os.offline_orders import verify_bundle

        verified = verify_bundle(raw, keyring)
    except Exception as exc:
        raise ValueError("offline_order_bundle_existing_invalid") from exc
    _require_bundle_scope(verified, config, verified["manifest"]["lease_epoch"])
    return verified


def _verify_bootstrap_bundle(
    bundle: dict[str, Any], keyring: dict[str, Any], config: Any, epoch: int
) -> dict[str, Any]:
    try:
        from restaurant_os.offline_orders import verify_bundle

        verified = verify_bundle(bundle, keyring)
    except Exception as exc:
        raise ValueError("offline_order_bootstrap_bundle_invalid") from exc
    _require_bundle_scope(verified, config, epoch)
    return verified


def _require_bundle_scope(bundle: dict[str, Any], config: Any, epoch: int) -> None:
    manifest = bundle.get("manifest")
    if not isinstance(manifest, dict) or any(
        manifest.get(field) != expected
        for field, expected in (
            ("organization_id", config.organization_id),
            ("branch_id", config.branch_id),
            ("device_id", config.source_device_id),
            ("lease_epoch", epoch),
        )
    ):
        raise ValueError("offline_order_bootstrap_scope_invalid")


def _operational_order_data_exists(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("order_database_invalid")
    return _database_has_rows(
        path,
        (
            "orders",
            "order_lines",
            "payments",
            "production_tasks",
            "order_line_consumption_snapshots",
            "inventory_movements",
            "local_order_commands",
        ),
    )


def _installed_bundle_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("order_database_invalid")
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as connection:
            if not _table_exists(connection, "offline_order_catalog_installations"):
                return None
            row = connection.execute(
                "SELECT bundle_hash FROM offline_order_catalog_installations LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise ValueError("order_database_inspection_failed") from exc
    if row is None or not isinstance(row[0], str) or len(row[0]) != 64:
        raise ValueError("order_database_inspection_failed")
    return row[0]


def _database_has_rows(path: Path, tables: tuple[str, ...]) -> bool:
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as connection:
            return any(
                _table_exists(connection, table)
                and connection.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() is not None
                for table in tables
            )
    except sqlite3.Error as exc:
        raise ValueError("order_database_inspection_failed") from exc


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _write_new_bundle(path: Path, bundle: dict[str, Any]) -> None:
    payload = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as exc:
            raise ValueError("offline_order_bundle_target_exists") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def create_order_service(config_path: Path, config: Any, keyring: dict[str, Any]) -> Any:
    """Validate signed input before touching local domain storage."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from restaurant_os.offline_order_catalog import hydrate_bundle
    from restaurant_os.offline_orders import verify_bundle

    from edge_gateway.order_outbox import OrderOutbox
    from edge_gateway.order_service import LocalOrderService

    paths = load_order_runtime_paths(config_path, config.runtime_root)
    if paths is None:
        return None
    bundle = verify_bundle(json.loads(paths.bundle.read_text(encoding="utf-8")), keyring)
    bindings = {
        "organization_id": config.organization_id,
        "branch_id": config.branch_id,
        "device_id": config.source_device_id,
    }
    if any(bundle["manifest"].get(key) != value for key, value in bindings.items()):
        raise ValueError("gateway order bundle scope differs from configuration")
    pem = load_gateway_credential(paths.signing_key, runtime_root=config.runtime_root)
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("gateway order signing key must be Ed25519")
    outbox = OrderOutbox(paths.database)
    catalog = OrderOutbox(paths.catalog_database)
    try:
        from edge_gateway.order_lifecycle import recover_catalog_refresh

        recover_catalog_refresh(
            outbox,
            catalog_database=paths.catalog_database,
            bundle_path=paths.bundle,
            keyring=keyring,
        )
        bundle = verify_bundle(json.loads(paths.bundle.read_text(encoding="utf-8")), keyring)
        hydrate_bundle(outbox.engine, bundle, include_operational_seed=True)
        hydrate_bundle(catalog.engine, bundle, include_operational_seed=False)
        return LocalOrderService(outbox, catalog.engine, bundle, keyring, private_key)
    except Exception:
        outbox.engine.dispose()
        catalog.engine.dispose()
        raise

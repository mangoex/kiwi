"""Gateway-side durable handoff and catalog renewal orchestration."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os.offline_order_catalog import refresh_catalog_snapshot
from restaurant_os.offline_orders import verify_bundle

from edge_gateway.order_outbox import OrderOutbox


def handoff_gateway(
    outbox: OrderOutbox,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    lease_epoch: int,
    private_key: Ed25519PrivateKey,
    send: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Freeze, sign and submit one immutable epoch manifest.

    Network failures intentionally leave the outbox FROZEN; rerunning uses the
    same signed payload and therefore cannot open a second authority handoff.
    """
    manifest = outbox.freeze_for_handoff(
        handoff_id=str(uuid4()),
        organization_id=organization_id,
        branch_id=branch_id,
        device_id=device_id,
        lease_epoch=lease_epoch,
    )
    signature = (
        base64.urlsafe_b64encode(private_key.sign(_canonical_manifest(manifest)))
        .decode()
        .rstrip("=")
    )
    outbox.save_handoff_signature(manifest["handoff_id"], signature)
    payload = outbox.handoff_payload()
    receipt = send(payload)
    if not isinstance(receipt, dict):
        raise ConnectionError("offline_handoff_response_invalid")
    outbox.acknowledge_handoff(receipt)
    return receipt


def renew_gateway_catalog(
    outbox: OrderOutbox,
    *,
    catalog_database: Path,
    bundle_path: Path,
    keyring: dict[str, Any],
    request_bundle: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Install an authorized same-epoch catalog without clearing operational facts."""
    bundle = request_bundle()
    verified = verify_bundle(bundle, keyring)
    previous = verify_bundle(json.loads(bundle_path.read_text(encoding="utf-8")), keyring)
    if any(
        verified["manifest"][field] != previous["manifest"][field]
        for field in ("organization_id", "branch_id", "device_id", "lease_epoch")
    ):
        raise ValueError("offline_catalog_refresh_scope_invalid")
    outbox.ensure_active_bundle(previous["hash"], previous["manifest"]["lease_epoch"])
    outbox.begin_catalog_refresh(verified, previous_bundle_hash=previous["hash"])
    try:
        refresh_catalog_snapshot(
            outbox.engine,
            manifest=verified["manifest"],
            catalog=verified["catalog"],
            operational_seed=verified["operational_seed"],
        )
        _replace_catalog_database(catalog_database, verified)
        _replace_bundle(bundle_path, verified)
        outbox.complete_catalog_refresh()
        return verified
    except Exception:
        # The REFRESHING journal retains the verified candidate.  Startup can
        # complete this exact installation without accepting another command.
        raise


def recover_catalog_refresh(
    outbox: OrderOutbox,
    *,
    catalog_database: Path,
    bundle_path: Path,
    keyring: dict[str, Any],
) -> dict[str, Any] | None:
    candidate = outbox.pending_catalog_refresh()
    if candidate is None:
        return None
    verified = verify_bundle(candidate, keyring)
    refresh_catalog_snapshot(
        outbox.engine,
        manifest=verified["manifest"],
        catalog=verified["catalog"],
        operational_seed=verified["operational_seed"],
    )
    _replace_catalog_database(catalog_database, verified)
    _replace_bundle(bundle_path, verified)
    outbox.complete_catalog_refresh()
    return verified


def recover_gateway_catalog(
    outbox: OrderOutbox,
    *,
    catalog_database: Path,
    bundle_path: Path,
    keyring: dict[str, Any],
    bundle: dict[str, Any],
    handoff_id: str,
    expected_previous_epoch: int,
) -> dict[str, Any]:
    verified = verify_bundle(bundle, keyring)
    outbox.begin_recovery_refresh(
        verified,
        handoff_id=handoff_id,
        expected_previous_epoch=expected_previous_epoch,
    )
    recovered = recover_catalog_refresh(
        outbox,
        catalog_database=catalog_database,
        bundle_path=bundle_path,
        keyring=keyring,
    )
    if recovered is None:
        raise ValueError("offline_recovery_journal_missing")
    return recovered


def _canonical_manifest(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _replace_catalog_database(path: Path, bundle: dict[str, Any]) -> None:
    """Build a separate verified catalog, then atomically replace only it."""
    from restaurant_os.offline_order_catalog import hydrate_catalog_snapshot

    if path.exists() and (path.is_symlink() or path.stat().st_nlink != 1):
        raise ValueError("offline_catalog_target_unsafe")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.refresh.", dir=path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        engine = sa.create_engine(f"sqlite:///{temporary_path}")
        try:
            hydrate_catalog_snapshot(
                engine,
                manifest=bundle["manifest"],
                catalog=bundle["catalog"],
                operational_seed=bundle["operational_seed"],
                read_only=True,
            ).close()
        finally:
            engine.dispose()
        _fsync_file(temporary_path)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _replace_bundle(path: Path, bundle: dict[str, Any]) -> None:
    if path.is_symlink() or (path.exists() and path.stat().st_nlink != 1):
        raise ValueError("offline_order_bundle_target_unsafe")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.refresh.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(bundle, target, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _fsync_file(path: Path) -> None:
    """Flush a replacement file after SQLite has closed all descriptors."""
    # Windows rejects FlushFileBuffers on a read-only descriptor.
    with path.open("r+b") as source:
        os.fsync(source.fileno())


def _fsync_directory(path: Path) -> None:
    """Persist a POSIX rename before an authority transition.

    Windows has no portable directory handle/fsync equivalent in Python. The
    atomic replacement still applies there; the gateway keeps REFRESHING until
    its next durable lifecycle transition, while POSIX makes the rename durable
    explicitly before it can return to ACTIVE.
    """
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

"""Synthetic local ORD-OFF-001 gateway for browser E2E; never contacts central."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import sqlalchemy as sa
import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "apps" / "api"),
    str(ROOT / "apps" / "edge-gateway"),
    str(ROOT / "apps" / "api" / "tests"),
]


def request(url: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    with httpx.Client(timeout=3, trust_env=False) as client:
        response = client.get(url, headers=headers or {})
    if response.status_code >= 400:
        raise RuntimeError(f"gateway_http_{response.status_code}:{response.text}")
    return response.status_code, response.json()


def main() -> None:
    from edge_gateway.runtime import create_gateway_runtime
    from restaurant_os import models
    from restaurant_os.offline_order_catalog import (
        build_catalog_snapshot,
        build_operational_seed,
    )
    from restaurant_os.offline_orders import sign_bundle
    from test_cash_concepts import ORG_ID
    from test_cash_ledger import BRANCH_A
    from test_combo_compositions import ACTOR
    from test_gateway_order_runtime import (
        DEVICE_ID,
        _bundle_source,
        _order_grant,
        _runtime_config,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    source_engine, source, _, _ = _bundle_source()
    temp = tempfile.TemporaryDirectory(prefix="restaurantos-offline-e2e-")
    server: uvicorn.Server | None = None
    try:
        now = datetime.now(UTC).replace(microsecond=0)
        role_id = source.scalar(
            sa.select(models.user_roles.c.role_id).where(models.user_roles.c.user_id == ACTOR)
        )
        source.execute(
            models.permissions.insert().values(
                id="e2e-kds", code="kds.tasks.operate", description="e2e", created_at=now
            )
        )
        source.execute(
            models.role_permissions.insert().values(role_id=role_id, permission_id="e2e-kds")
        )
        for code in ("payments.confirm", "pos.operate", "cash.shift.read", "orders.fulfill"):
            permission_id = source.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            if permission_id is None:
                permission_id = str(uuid4())
                source.execute(
                    models.permissions.insert().values(
                        id=permission_id, code=code, description=code, created_at=now
                    )
                )
            if (
                source.execute(
                    sa.select(models.role_permissions).where(
                        models.role_permissions.c.role_id == role_id,
                        models.role_permissions.c.permission_id == permission_id,
                    )
                ).first()
                is None
            ):
                source.execute(
                    models.role_permissions.insert().values(
                        role_id=role_id, permission_id=permission_id
                    )
                )
        source.commit()
        catalog = build_catalog_snapshot(source, organization_id=ORG_ID, branch_id=BRANCH_A)
        seed = build_operational_seed(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, actor_ids=[ACTOR]
        )
        central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        manifest = {
            "schema_version": "ord-off/v1",
            "organization_id": ORG_ID,
            "branch_id": BRANCH_A,
            "device_id": DEVICE_ID,
            "bundle_id": str(uuid4()),
            "lease_epoch": 1,
            "issued_at": int(now.timestamp()),
            "expires_at": int((now + timedelta(hours=2)).timestamp()),
        }
        bundle = sign_bundle(
            {"manifest": manifest, "catalog": catalog, "operational_seed": seed},
            central_key,
            kid="central",
        )
        config_path = _runtime_config(Path(temp.name), central_key, device_key, bundle)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["central_url"] = "http://127.0.0.1:9"
        config["pos_origin"] = "http://127.0.0.1:4177"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        grant = _order_grant(
            central_key, manifest=bundle["manifest"], bundle_hash=bundle["hash"], now=now
        )
        runtime = create_gateway_runtime(config_path, worker_interval_seconds=60)
        server = uvicorn.Server(
            uvicorn.Config(runtime.app, host="127.0.0.1", port=args.port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        status_url = f"http://127.0.0.1:{args.port}/api/v1/local/orders/status"
        for _ in range(50):
            try:
                status, body = request(status_url)
                if status == 200 and body.get("ready"):
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("gateway_fixture_not_ready")
        headers = {"Authorization": f"Offline {grant}", "Origin": "http://127.0.0.1:4177"}
        assert (
            request(f"http://127.0.0.1:{args.port}/api/v1/local/order-api/auth/session", headers)[0]
            == 200
        )
        assert (
            request(
                f"http://127.0.0.1:{args.port}/api/v1/local/order-api/catalog/products", headers
            )[0]
            == 200
        )
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(
            json.dumps(
                {
                    "gateway_url": f"http://127.0.0.1:{args.port}",
                    "grant": grant,
                    "branch_id": BRANCH_A,
                    "device_id": DEVICE_ID,
                    "bundle_id": bundle["manifest"]["bundle_id"],
                    "lease_epoch": 1,
                }
            ),
            encoding="utf-8",
        )
        signal.signal(signal.SIGTERM, lambda *_: setattr(server, "should_exit", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(server, "should_exit", True))
        thread.join()
    finally:
        if server:
            server.should_exit = True
        source.close()
        source_engine.dispose()
        temp.cleanup()


if __name__ == "__main__":
    main()

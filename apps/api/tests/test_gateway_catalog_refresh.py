"""Catalog renewal preserves open orders and recovers interrupted publication."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway import order_lifecycle
from restaurant_os import models
from restaurant_os.offline_order_catalog import build_catalog_snapshot
from restaurant_os.offline_orders import sign_bundle
from sqlalchemy.orm import Session
from test_gateway_order_runtime import (
    BRANCH_A,
    COMBO,
    DEVICE_ID,
    ORG_ID,
    _bundle_source,
    _Client,
    _order_grant,
    _runtime_config,
    create_gateway_runtime,
)


@pytest.mark.parametrize("catalog_schema", ["ord-off-catalog/v2", "ord-off-catalog/v3"])
@pytest.mark.parametrize("crash", [False, True])
def test_renewal_preserves_open_order_and_rejects_an_already_open_old_service(
    tmp_path, monkeypatch, crash, catalog_schema
):
    engine, source, catalog, seed = _bundle_source()
    catalog = build_catalog_snapshot(
        source,
        organization_id=ORG_ID,
        branch_id=BRANCH_A,
        catalog_schema=catalog_schema,
    )
    central, device = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    now = datetime.now(UTC).replace(microsecond=0)
    manifest = {
        "schema_version": "ord-off/v1",
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": DEVICE_ID,
        "bundle_id": str(uuid4()),
        "lease_epoch": 1,
        "issued_at": int(now.timestamp()),
        "expires_at": int(now.timestamp()) + 7200,
    }
    if catalog_schema.endswith("v3"):
        manifest.update(catalog_generation=1, catalog_classification_mode="legacy")
    bundle = sign_bundle(
        {"manifest": manifest, "catalog": catalog, "operational_seed": seed}, central, kid="central"
    )
    config = _runtime_config(tmp_path, central, device, bundle)
    runtime = create_gateway_runtime(config, client_factory=_Client)
    restarted = None
    try:
        service = runtime.order_service
        old_grant = _order_grant(
            central, manifest=bundle["manifest"], bundle_hash=bundle["hash"], now=now
        )
        payload = {"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"}
        order = service.execute(old_grant, "create", payload, "refresh-open-order-001", now=now)
        command_id = order["_offline"]["command_id"]
        service.outbox.resolve(command_id, status="CONFIRMED", checkpoint=1)
        with Session(service.outbox.engine) as session:
            snapshots = [
                dict(row)
                for row in session.execute(
                    sa.select(models.order_line_consumption_snapshots)
                ).mappings()
            ]
            movements = [
                dict(row)
                for row in session.execute(sa.select(models.inventory_movements)).mappings()
            ]
        source.execute(
            models.price_versions.update()
            .where(models.price_versions.c.product_id == COMBO)
            .values(price_cents=9999)
        )
        source.commit()
        next_bundle = sign_bundle(
            {
                "manifest": {
                    **manifest,
                    "bundle_id": str(uuid4()),
                    **({"catalog_generation": 2} if catalog_schema.endswith("v3") else {}),
                },
                "catalog": build_catalog_snapshot(
                    source,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    catalog_schema=catalog_schema,
                ),
                "operational_seed": seed,
            },
            central,
            kid="central",
        )
        options = dict(
            catalog_database=tmp_path / "catalog.db",
            bundle_path=tmp_path / "orders-bundle.json",
            keyring={"central": central.public_key()},
            request_bundle=lambda: next_bundle,
        )
        if crash:
            with monkeypatch.context() as fault:

                def fail(*_):
                    raise OSError("injected publication crash")

                fault.setattr(order_lifecycle, "_replace_bundle", fail)
                with pytest.raises(OSError, match="publication crash"):
                    order_lifecycle.renew_gateway_catalog(service.outbox, **options)
            assert service.outbox.lifecycle_status() == "REFRESHING"
        else:
            order_lifecycle.renew_gateway_catalog(service.outbox, **options)
        runtime.shutdown()
        restarted = create_gateway_runtime(config, client_factory=_Client)
        fresh = restarted.order_service
        with pytest.raises(ValueError, match="stale_bundle"):
            service.execute(old_grant, "create", payload, "refresh-old-process-001", now=now)
        with Session(fresh.outbox.engine) as session:
            assert (
                session.scalar(
                    sa.select(models.orders.c.total_cents).where(models.orders.c.id == order["id"])
                )
                == 15900
            )
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
            assert [
                dict(row)
                for row in session.execute(
                    sa.select(models.order_line_consumption_snapshots)
                ).mappings()
            ] == snapshots
            assert [
                dict(row)
                for row in session.execute(sa.select(models.inventory_movements)).mappings()
            ] == movements
        if catalog_schema.endswith("v3"):
            from restaurant_os.operations import BusinessError

            with pytest.raises(BusinessError, match="Signature is invalid"):
                order_lifecycle.renew_gateway_catalog(
                    fresh.outbox,
                    **{
                        **options,
                        "request_bundle": lambda: {**next_bundle, "signature": "invalid"},
                    },
                )
            assert fresh.outbox.lifecycle_status() == "ACTIVE"
            with pytest.raises(BusinessError, match="generation rejected"):
                order_lifecycle.renew_gateway_catalog(
                    fresh.outbox,
                    **{**options, "request_bundle": lambda: bundle},
                )
            assert fresh.outbox.lifecycle_status() == "ACTIVE"
        grant = _order_grant(
            central, manifest=next_bundle["manifest"], bundle_hash=next_bundle["hash"], now=now
        )
        new_order = fresh.execute(grant, "create", payload, "refresh-new-process-001", now=now)
        assert new_order["total_cents"] == 9999
        assert fresh.outbox.get(command_id)["status"] == "CONFIRMED"
    finally:
        if restarted:
            restarted.shutdown()
        runtime.shutdown()
        source.close()
        engine.dispose()

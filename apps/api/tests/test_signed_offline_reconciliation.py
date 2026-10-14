"""Real crypto/domain reconciliation rejects authority drift without losing durable ACKs."""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import models, operations
from restaurant_os.config import get_settings
from restaurant_os.offline_orders import reconcile_order_command
from sqlalchemy.orm import Session
from test_cash_ledger import BRANCH_A, CASHIER_ID, _new_session, _withdrawal_concept
from test_combo_compositions import ACTOR
from test_domain_offline_orders import ACCEPTED_AT
from test_offline_authorization_registry import _device
from test_offline_order_reconcile_conflicts import _central_and_pending_envelopes
from test_pco008_cash_sync import _envelope


@pytest.fixture(autouse=True)
def signed_protocol(monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _cash_command(monkeypatch, signed=True, database_url="sqlite+pysqlite://"):
    monkeypatch.setenv("RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED", str(signed).lower())
    get_settings.cache_clear()
    engine, session = _new_session(database_url)
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(operations, "_offline_grant_signing_material", lambda: (key, "qa"))
    monkeypatch.setattr(operations, "_offline_grant_keyring", lambda: {"qa": key.public_key()})
    concept = _withdrawal_concept(session)
    device = _device(session, BRANCH_A)
    grant = operations.issue_offline_cash_grant(
        session,
        actor_user_id=CASHIER_ID,
        organization_id=operations.ORGANIZATION_ID,
        branch_id=BRANCH_A,
        source_device_id=device,
    )
    accepted = datetime.now(UTC).isoformat()
    command = _envelope(
        str(concept["id"]),
        offline_grant=grant["offline_grant"],
        source_device_id=device,
        occurred_at=accepted,
        accepted_at=accepted,
    )
    return engine, session, device, command


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("version", "offline_authorization_version_stale"),
        ("missing", "offline_authorization_unregistered"),
        ("unknown", "offline_authorization_version_missing"),
        ("revoked", "offline_authorization_revoked"),
    ],
)
def test_cash_new_command_requires_registered_current_authority(monkeypatch, mutation, code):
    engine, session, device, command = _cash_command(monkeypatch)
    try:
        if mutation == "version":
            session.execute(
                models.users.update()
                .where(models.users.c.id == CASHIER_ID)
                .values(
                    authorization_version=2,
                )
            )
        elif mutation == "missing":
            session.execute(models.offline_authorization_leases.delete())
        elif mutation == "unknown":
            session.execute(
                models.offline_authorization_leases.update().values(
                    authorization_version=None,
                    provenance="retained_legacy",
                )
            )
        else:
            session.execute(
                models.offline_authorization_leases.update().values(
                    state="revoked",
                    revoked_at=datetime.now(UTC),
                )
            )
        session.commit()
        result = operations.receive_sync_command(session, command, actor_device_id=device)
        assert result["status"] == "CONFLICT"
        assert result["code"] == code
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(models.sync_events)) == 0
    finally:
        session.close()
        engine.dispose()


def test_cash_exact_confirmed_ack_survives_actor_and_key_retirement(monkeypatch):
    engine, session, device, command = _cash_command(monkeypatch)
    try:
        first = operations.receive_sync_command(session, command, actor_device_id=device)
        assert first["status"] == "CONFIRMED"
        session.execute(
            models.users.update()
            .where(models.users.c.id == CASHIER_ID)
            .values(
                status="inactive",
                authorization_version=2,
            )
        )
        session.commit()

        def retired():
            pytest.fail("persisted cash ACK loaded retired key material")

        monkeypatch.setattr(operations, "_offline_grant_keyring", retired)
        result = operations.receive_sync_command(session, command, actor_device_id=device)
        assert result["replayed"] is True
        assert result["movement"] == first["movement"]
        assert set(result["movement"]) == {"id", "status"}
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
    finally:
        session.close()
        engine.dispose()


def test_order_new_command_rejects_version_change_even_with_same_permissions(tmp_path):
    engine, command, _, keys, _ = _central_and_pending_envelopes(tmp_path)
    try:
        with Session(engine) as session:
            session.execute(
                models.users.update()
                .where(models.users.c.id == ACTOR)
                .values(
                    authorization_version=2,
                )
            )
            session.commit()
            result = reconcile_order_command(
                session, command, keyring=keys, now=ACCEPTED_AT, commit=True
            )
            assert result["status"] == "conflict"
            assert result["code"] == "offline_authorization_version_stale"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.inventory_movements))
                == 0
            )
    finally:
        engine.dispose()


def test_legacy_emission_control_does_not_disable_reconciliation_fence(monkeypatch):
    import base64
    import json

    engine, session, device, command = _cash_command(monkeypatch, signed=False)
    try:
        part = command["offline_grant"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        assert claims["version"] == 2
        assert "authorization_version" not in claims
        session.execute(
            models.users.update()
            .where(models.users.c.id == CASHIER_ID)
            .values(
                authorization_version=2,
            )
        )
        session.commit()
        result = operations.receive_sync_command(session, command, actor_device_id=device)
        assert result["code"] == "offline_authorization_version_stale"
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0
    finally:
        session.close()
        engine.dispose()


def test_new_signed_command_requires_registry_even_without_mobility(monkeypatch):
    engine, session, device, command = _cash_command(monkeypatch)
    try:
        session.rollback()
        models.offline_authorization_leases.drop(engine)
        models.offline_authorization_rollouts.drop(engine)
        monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "false")
        get_settings.cache_clear()
        result = operations.receive_sync_command(session, command, actor_device_id=device)
        assert result["code"] == "offline_authorization_registry_required"
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0
        from restaurant_os.operations import BusinessError

        with pytest.raises(BusinessError) as issuer:
            operations.issue_offline_cash_grant(
                session,
                actor_user_id=CASHIER_ID,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_A,
                source_device_id=device,
            )
        assert issuer.value.code == "offline_authorization_registry_required"
    finally:
        session.close()
        engine.dispose()


def test_authenticated_order_ack_survives_epoch_and_key_retirement(tmp_path):
    from restaurant_os.operations import BusinessError

    engine, command, _, keys, _ = _central_and_pending_envelopes(tmp_path)
    try:
        with Session(engine) as session:
            first = reconcile_order_command(
                session,
                command,
                keyring=keys,
                now=ACCEPTED_AT,
                commit=True,
            )
            session.execute(models.offline_order_gateway_leases.update().values(lease_epoch=2))
            session.execute(
                models.users.update()
                .where(models.users.c.id == ACTOR)
                .values(
                    status="inactive",
                    authorization_version=2,
                )
            )
            session.commit()

            def retired():
                pytest.fail("authenticated persisted ACK loaded retired material")

            replay = reconcile_order_command(
                session,
                command,
                keyring=retired,
                now=ACCEPTED_AT,
                authenticated_device_id=command["device_id"],
            )
            assert replay == first
            with pytest.raises(BusinessError) as rejected:
                reconcile_order_command(
                    session,
                    command,
                    keyring=keys,
                    now=ACCEPTED_AT,
                )
            assert rejected.value.code == "offline_gateway_lease_invalid"
            session.rollback()
            with pytest.raises(BusinessError) as foreign:
                reconcile_order_command(
                    session,
                    command,
                    keyring=retired,
                    now=ACCEPTED_AT,
                    authenticated_device_id="foreign-device",
                )
            assert foreign.value.code == "device_scope_denied"
    finally:
        engine.dispose()


def test_verification_result_cannot_fall_back_to_legacy_after_key_rotation(monkeypatch):
    engine, session, device, command = _cash_command(monkeypatch)
    try:
        session.rollback()
        models.offline_authorization_leases.drop(engine)
        models.offline_authorization_rollouts.drop(engine)
        original_keys = operations._offline_grant_keyring()
        rings = iter([original_keys, {}])
        monkeypatch.setattr(operations, "_offline_grant_keyring", lambda: next(rings, {}))
        monkeypatch.setenv("RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED", "false")
        get_settings.cache_clear()
        result = operations.receive_sync_command(session, command, actor_device_id=device)
        assert result["status"] == "CONFLICT"
        assert result["code"] == "offline_authorization_registry_required"
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0
    finally:
        session.close()
        engine.dispose()


def test_gateway_new_grant_cannot_replace_frozen_seed_authority(tmp_path):
    from edge_gateway.order_outbox import OrderOutbox
    from edge_gateway.order_service import LocalOrderService
    from restaurant_os.offline_orders import _retained_bundle, _sign_grant, verify_order_grant
    from restaurant_os.operations import BusinessError

    engine, command, _, keys, device = _central_and_pending_envelopes(tmp_path)
    try:
        with Session(engine) as session:
            bundle = _retained_bundle(session, command)
        # Only the new authority claim differs; the original frozen signed seed remains version 1.
        claims = verify_order_grant(command["grant"], keys, ACCEPTED_AT)
        assert claims["schema_version"] == "ord-off-grant/v4"
        claims["authorization_version"] = 2
        key = Ed25519PrivateKey.generate()
        token = _sign_grant(claims, key, kid="new")
        outbox = OrderOutbox(tmp_path / "orders.db")
        catalog = OrderOutbox(tmp_path / "catalog.db")
        local = LocalOrderService(
            outbox, catalog.engine, bundle, {**keys, "new": key.public_key()}, device
        )
        before = len(outbox.pending())
        with pytest.raises(BusinessError) as stale:
            local.execute(
                token,
                "create",
                command["payload"],
                "stale-authority-local",
                now=ACCEPTED_AT,
            )
        assert stale.value.code == "offline_bundle_authority_stale"
        assert len(outbox.pending()) == before
        outbox.engine.dispose()
        catalog.engine.dispose()
    finally:
        engine.dispose()


@pytest.mark.parametrize("domain", ["cash", "orders"])
@pytest.mark.parametrize(
    "rollback_fails", [False, True], ids=["normal-rollback", "failed-rollback"],
)
def test_persistence_failure_rolls_back_and_redacts_signed_evidence(
    monkeypatch, tmp_path, domain, rollback_fails,
):
    from restaurant_os import offline_orders
    from restaurant_os.operations import BusinessError

    database_url = sa.URL.create("sqlite+pysqlite", database=str(tmp_path / "durable-central.db"))
    if domain == "cash":
        engine, session, device, command = _cash_command(monkeypatch, database_url=database_url)
        token = command["offline_grant"]
    else:
        engine, command, _, keys, _ = _central_and_pending_envelopes(tmp_path, database_url)
        session = Session(engine)
        token = command["grant"]
    fault = sa.exc.OperationalError(
        "synthetic persistence", {"grant": token}, RuntimeError("fault")
    )
    if rollback_fails:
        def unavailable_rollback():
            raise fault

        monkeypatch.setattr(session, "rollback", unavailable_rollback)
    insert = offline_orders._insert_reconciliation_receipt

    def cash_fault(point):
        if point == "after_audit":
            raise fault

    def order_fault(*args, **kwargs):
        insert(*args, **kwargs)
        raise fault

    monkeypatch.setattr(operations, "_pco008_fault", cash_fault)
    monkeypatch.setattr(offline_orders, "_insert_reconciliation_receipt", order_fault)
    try:
        with pytest.raises(BusinessError) as rejected:
            if domain == "cash":
                operations.receive_sync_command(session, command, actor_device_id=device)
            else:
                reconcile_order_command(
                    session, command, keyring=keys, now=ACCEPTED_AT, commit=True
                )
        assert rejected.value.code == "offline_reconciliation_persistence_unavailable"
        assert token not in str(rejected.value)
        assert rejected.value.__suppress_context__ is True
        assert not session.in_transaction()
        effect = models.cash_movements if domain == "cash" else models.orders
        inbox = models.sync_commands if domain == "cash" else models.offline_order_inbox
        assert session.scalar(sa.select(sa.func.count()).select_from(effect)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(inbox)) == 0
    finally:
        session.close()
        engine.dispose()


def test_order_confirmed_exact_ack_does_not_renew_human_authority(tmp_path):
    engine, command, _, keys, _ = _central_and_pending_envelopes(tmp_path)
    try:
        with Session(engine) as session:
            first = reconcile_order_command(
                session, command, keyring=keys, now=ACCEPTED_AT, commit=True
            )
            assert first["status"] == "confirmed"
            session.execute(
                models.users.update()
                .where(models.users.c.id == ACTOR)
                .values(
                    status="inactive",
                    authorization_version=2,
                )
            )
            session.commit()
            replay = reconcile_order_command(
                session, command, keyring=keys, now=ACCEPTED_AT, commit=True
            )
            assert replay == first
            assert set(replay) == {"command_id", "status", "checkpoint", "code"}
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
    finally:
        engine.dispose()

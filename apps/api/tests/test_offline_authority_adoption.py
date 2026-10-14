"""Controlled cutover uses synthetic evidence; never activates a real organization."""

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import offline_adoption as adoption
from restaurant_os import offline_authorization as authority
from restaurant_os import operations as ops
from restaurant_os.offline_adoption import prepare_offline_adoption
from restaurant_os.offline_authorization import (
    _utc,
    assert_transition_allowed,
    reconciliation_authority_error,
)
from restaurant_os.order_execution import ExecutionContext, order_execution_context
from test_branch_workspace_authority import workspace as workspace
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID

NOW = datetime(2026, 10, 14, 8, tzinfo=timezone.utc)
KEY = "offline-cutover-synthetic-001"
PAYLOAD = {"retired_unregistered_issuers": True, "retirement_evidence_sha256": "a" * 64}


def _clock(monkeypatch, clock):
    monkeypatch.setattr(adoption, "authority_now", clock)
    monkeypatch.setattr(authority, "authority_now", clock)


def _unprepared(factory):
    with factory() as session:
        session.execute(
            models.role_authority_grants.insert().values(
                role_id=ADMIN_ROLE_ID,
                authority_kind="organization_all_permissions",
                created_at=NOW,
            )
        )
        session.execute(
            models.offline_authorization_rollouts.update().values(
                state="unprepared",
                registration_started_at=None,
                legacy_drain_until=None,
            )
        )
        session.commit()


def test_preparation_is_durable_exact_replay_and_never_backdates(workspace, monkeypatch):
    _, _, factory, _ = workspace
    _unprepared(factory)
    _clock(monkeypatch, lambda: NOW)
    with factory() as session:
        receipt = prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
        assert receipt["state"] == "draining"
        assert receipt["registration_started_at"] == NOW.isoformat()
        assert receipt["legacy_drain_until"] == (NOW + timedelta(hours=2)).isoformat()
    _clock(monkeypatch, lambda: NOW + timedelta(hours=1))
    with factory() as session:
        assert prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY) == receipt
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_cutovers)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "auth.offline_adoption_prepared")
            )
            == 1
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"retired_unregistered_issuers": False},
        {"retired_unregistered_issuers": 1},
        {"retirement_evidence_sha256": ""},
        {"retirement_evidence_sha256": "z" * 64},
        {"registration_started_at": NOW.isoformat()},
        {"state": "clean_install"},
    ],
)
def test_unproven_or_client_selected_readiness_is_rejected(workspace, patch):
    _, _, factory, _ = workspace
    _unprepared(factory)
    with factory() as session:
        with pytest.raises(ops.BusinessError) as exc:
            prepare_offline_adoption(session, ADMIN_USER_ID, {**PAYLOAD, **patch}, KEY)
        assert exc.value.code == "offline_adoption_payload_invalid"
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )


def test_cutover_is_not_restarted_by_another_command(workspace, monkeypatch):
    _, _, factory, _ = workspace
    _unprepared(factory)
    _clock(monkeypatch, lambda: NOW)
    with factory() as session:
        first = prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
    with factory() as session:
        with pytest.raises(ops.BusinessError) as exc:
            prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY + "-different")
        assert exc.value.code == "offline_adoption_command_conflict"
        assert _utc(
            session.scalar(sa.select(models.offline_authorization_cutovers.c.legacy_drain_until))
        ) == datetime.fromisoformat(first["legacy_drain_until"])


def test_last_drain_second_blocks_and_unproven_manual_state_cannot_enable(workspace, monkeypatch):
    _, fixture, factory, _ = workspace
    _unprepared(factory)
    _clock(monkeypatch, lambda: NOW)
    with factory() as session:
        prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
    _clock(monkeypatch, lambda: NOW + timedelta(hours=2))
    with factory() as session:
        with pytest.raises(ops.BusinessError) as exc:
            assert_transition_allowed(session, fixture["supervisor_id"], fixture["branch_id"])
        assert exc.value.code == "branch_offline_preflight_required"
    _clock(monkeypatch, lambda: NOW + timedelta(hours=2, seconds=1))
    with factory() as session:
        assert_transition_allowed(session, fixture["supervisor_id"], fixture["branch_id"])
    with factory() as session:
        session.execute(models.offline_authorization_cutovers.delete())
        session.commit()
    with factory() as session:
        with pytest.raises(ops.BusinessError) as exc:
            assert_transition_allowed(session, fixture["supervisor_id"], fixture["branch_id"])
        assert exc.value.code == "branch_offline_preflight_required"


@pytest.mark.parametrize("failure", ["audit", "commit"])
def test_failed_preparation_has_no_partial_readiness(workspace, monkeypatch, failure):
    _, _, factory, _ = workspace
    _unprepared(factory)
    _clock(monkeypatch, lambda: NOW)

    def failed(*args, **kwargs):
        raise sa.exc.OperationalError("synthetic sensitive SQL", {}, RuntimeError("failure"))

    with factory() as session:
        if failure == "audit":
            monkeypatch.setattr(ops, "_audit", failed)
        else:
            monkeypatch.setattr(session, "commit", failed)
        with pytest.raises(ops.BusinessError) as exc:
            prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
        assert exc.value.code == "offline_adoption_persistence_unavailable"
        assert "sensitive" not in str(exc.value)
    with factory() as session:
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_cutovers)
            )
            == 0
        )


def test_replay_revalidates_active_protected_authority(workspace, monkeypatch):
    _, _, factory, _ = workspace
    _unprepared(factory)
    _clock(monkeypatch, lambda: NOW)
    with factory() as session:
        prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
        session.execute(
            models.users.update()
            .where(models.users.c.id == ADMIN_USER_ID)
            .values(status="inactive")
        )
        session.commit()
    with factory() as session:
        with pytest.raises(ops.AuthorizationError) as exc:
            prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
        assert exc.value.code == "actor_not_authorized"


def test_clock_ignores_historical_order_acceptance(workspace):
    _, _, factory, _ = workspace
    _unprepared(factory)
    before = datetime.now(timezone.utc)
    context = ExecutionContext(
        command_id=ADMIN_USER_ID,
        accepted_at=before - timedelta(hours=10),
        execution_mode="offline_reconcile",
    )
    with factory() as session, order_execution_context(context):
        receipt = prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
    assert datetime.fromisoformat(receipt["registration_started_at"]) >= before
    with factory() as session:
        event = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "auth.offline_adoption_prepared"
                )
            )
            .mappings()
            .one()
        )
        assert event["branch_id"] is None


def test_business_rejection_with_failed_rollback_is_redacted(workspace, monkeypatch):
    _, _, factory, _ = workspace
    _unprepared(factory)
    with factory() as session:

        def failed():
            raise sa.exc.OperationalError("synthetic sensitive SQL", {}, RuntimeError("failure"))

        monkeypatch.setattr(session, "rollback", failed)
        with pytest.raises(ops.BusinessError) as exc:
            prepare_offline_adoption(
                session, ADMIN_USER_ID, {**PAYLOAD, "state": "clean_install"}, KEY
            )
        assert exc.value.code == "offline_adoption_payload_invalid"
        assert "sensitive" not in str(exc.value)


def test_retained_identity_is_imported_with_unknown_version_and_original_unchanged(
    workspace, monkeypatch
):
    from test_offline_authorization_registry import _order_fixture

    client, _, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    issued = client.post("/api/v1/offline-orders/grants", headers=headers, json=payload)
    assert issued.status_code == 200, issued.text
    with factory() as session:
        original = dict(session.execute(sa.select(models.offline_order_grants)).mappings().one())
        session.execute(models.offline_authorization_leases.delete())
        session.commit()
    _unprepared(factory)
    _clock(monkeypatch, lambda: _utc(original["issued_at"]) + timedelta(seconds=1))
    with factory() as session:
        prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
    with factory() as session:
        retained = dict(
            session.execute(sa.select(models.offline_authorization_leases)).mappings().one()
        )
        assert retained["provenance"] == "retained_legacy"
        assert retained["authorization_version"] is None
        assert retained["source_grant_id"] == original["id"]
        assert original["token"] not in str(retained)
        assert (
            dict(session.execute(sa.select(models.offline_order_grants)).mappings().one())
            == original
        )
        assert (
            reconciliation_authority_error(
                session,
                actor=original["actor_id"],
                branch=original["branch_id"],
                kind="orders",
                token=original["token"],
                device_id=original["device_id"],
                current_version=1,
                signed_version=1,
                bundle_id=original["bundle_id"],
                epoch=original["lease_epoch"],
            )
            == "offline_authorization_version_missing"
        )


@pytest.mark.parametrize("target", [None, "sqlite://", "malformed"])
def test_operator_cli_requires_explicit_postgres_without_connecting(monkeypatch, capsys, target):
    if target is None:
        monkeypatch.delenv("RESTAURANTOS_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("RESTAURANTOS_DATABASE_URL", target)

    def forbidden(*args, **kwargs):
        raise AssertionError("CLI must reject before opening a database")

    monkeypatch.setattr(adoption.sa, "create_engine", forbidden)
    assert (
        adoption.main(
            [
                "--actor-id",
                ADMIN_USER_ID,
                "--retirement-evidence-sha256",
                "a" * 64,
                "--idempotency-key",
                KEY,
                "--confirm-retired-unregistered-issuers",
            ]
        )
        == 1
    )
    assert capsys.readouterr().err.strip() == "offline_adoption_explicit_postgres_required"


@pytest.mark.parametrize("failure", ["bootstrap", "dispose"])
def test_operator_cli_redacts_engine_failures_before_emitting_receipt(monkeypatch, capsys, failure):
    from contextlib import contextmanager
    from types import SimpleNamespace

    target = sa.URL.create("postgresql+psycopg", host="127.0.0.1", database="corp_pur_synthetic")
    monkeypatch.setenv("RESTAURANTOS_DATABASE_URL", str(target))

    def failed(*args, **kwargs):
        raise sa.exc.OperationalError("sql-redaction-probe", {}, RuntimeError("failure"))

    @contextmanager
    def session(*args, **kwargs):
        yield object()

    monkeypatch.setattr(adoption, "Session", session)
    monkeypatch.setattr(adoption, "prepare_offline_adoption", lambda *args: {"state": "draining"})
    monkeypatch.setattr(
        adoption.sa,
        "create_engine",
        failed if failure == "bootstrap" else (lambda *args: SimpleNamespace(dispose=failed)),
    )
    assert (
        adoption.main(
            [
                "--actor-id",
                ADMIN_USER_ID,
                "--retirement-evidence-sha256",
                "a" * 64,
                "--idempotency-key",
                KEY,
                "--confirm-retired-unregistered-issuers",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == "offline_adoption_persistence_unavailable"


def test_cutover_migration_roundtrip_and_history_guard(workspace, monkeypatch):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    _, _, factory, _ = workspace
    _unprepared(factory)
    spec = importlib.util.spec_from_file_location(
        "cutover_migration_test",
        Path(__file__).parents[1] / "alembic/versions/202610140600_0089_offline_cutovers.py",
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory() as session:
        with Operations.context(MigrationContext.configure(session.connection())):
            migration.downgrade()
            migration.upgrade()
        session.commit()
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_cutovers)
            )
            == 0
        )
    _clock(monkeypatch, lambda: NOW)
    with factory() as session:
        prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
    with factory() as session:
        with Operations.context(MigrationContext.configure(session.connection())):
            with pytest.raises(RuntimeError, match="0089 downgrade blocked"):
                migration.downgrade()
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_cutovers)
            )
            == 1
        )
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "draining"
        )


@pytest.mark.parametrize("key", ["", "short", "x" * 181, " " + KEY])
def test_invalid_command_key_cannot_start_readiness(workspace, key):
    _, _, factory, _ = workspace
    _unprepared(factory)
    with factory() as session:
        with pytest.raises(ops.BusinessError) as exc:
            prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, key)
        assert exc.value.code == "idempotency_key_invalid"
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )


def test_invalid_later_source_rolls_back_all_prior_imports(workspace, monkeypatch):
    from test_offline_authorization_registry import _order_fixture

    client, _, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    issued = client.post("/api/v1/offline-orders/grants", headers=headers, json=payload)
    assert issued.status_code == 200, issued.text
    with factory() as session:
        original = dict(session.execute(sa.select(models.offline_order_grants)).mappings().one())
        session.execute(models.offline_authorization_leases.delete())
        session.execute(
            models.offline_order_grants.insert().values(
                **{**original, "id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "lease_epoch": 0}
            )
        )
        before = [
            dict(row)
            for row in session.execute(
                sa.select(models.offline_order_grants).order_by(models.offline_order_grants.c.id)
            ).mappings()
        ]
        session.commit()
    _unprepared(factory)
    _clock(monkeypatch, lambda: _utc(original["issued_at"]) + timedelta(seconds=1))
    with factory() as session:
        with pytest.raises(ops.BusinessError) as exc:
            prepare_offline_adoption(session, ADMIN_USER_ID, PAYLOAD, KEY)
        assert exc.value.code == "offline_adoption_retained_invalid"
    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_leases)
            )
            == 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_cutovers)
            )
            == 0
        )
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )
        assert [
            dict(row)
            for row in session.execute(
                sa.select(models.offline_order_grants).order_by(models.offline_order_grants.c.id)
            ).mappings()
        ] == before


def test_workspace_grant_does_not_grant_cutover_authority(workspace):
    _, fixture, factory, _ = workspace
    _unprepared(factory)
    with factory() as session:
        with pytest.raises(ops.AuthorizationError) as exc:
            prepare_offline_adoption(session, fixture["supervisor_id"], PAYLOAD, KEY)
        assert exc.value.code == "owner_authority_required"
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )

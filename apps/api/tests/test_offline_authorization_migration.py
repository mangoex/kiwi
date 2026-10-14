# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-offline-authorization-migration-tests-v1
"""0088 expands without inferring historical version or writer readiness."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from restaurant_os import models, operations
from test_branch_workspace_authority import workspace as workspace
from test_offline_authorization_registry import _cash_grant, _order_fixture


def _migration(connection):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/202610140400_0088_offline_authorization.py"
    )
    spec = importlib.util.spec_from_file_location("offline_authorization_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(connection))
    return module


def test_additive_registry_keeps_legacy_grant_and_starts_unprepared(workspace, monkeypatch):
    _, fixture, factory, _, payload = _order_fixture(workspace, monkeypatch)
    with factory() as session:
        bundle = session.execute(sa.select(models.offline_order_bundles)).mappings().one()
        session.execute(
            models.offline_order_grants.insert().values(
                id=operations._id(),
                organization_id=operations.ORGANIZATION_ID,
                branch_id=fixture["branch_id"],
                device_id=payload["source_device_id"],
                actor_id=fixture["supervisor_id"],
                bundle_id=payload["bundle_id"],
                bundle_hash=bundle["bundle_hash"],
                lease_epoch=1,
                capabilities=["orders.create"],
                token="synthetic-retained-legacy-token",
                issued_at=bundle["issued_at"],
                expires_at=bundle["expires_at"],
            )
        )
        # Fixture rollback setup only; production readiness remains protected evidence.
        session.execute(
            models.offline_authorization_rollouts.update().values(
                state="unprepared",
                registration_started_at=None,
                legacy_drain_until=None,
            )
        )
        session.commit()
    with factory().get_bind().begin() as connection:
        original = dict(connection.execute(sa.select(models.offline_order_grants)).mappings().one())
        migration = _migration(connection)
        migration.downgrade()
        for _ in range(2):
            migration.upgrade()
            rollout = (
                connection.execute(sa.select(models.offline_authorization_rollouts))
                .mappings()
                .one()
            )
            assert rollout["state"] == "unprepared"
            assert rollout["registration_started_at"] is None
            assert rollout["legacy_drain_until"] is None
            assert (
                dict(connection.execute(sa.select(models.offline_order_grants)).mappings().one())
                == original
            )
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(models.offline_authorization_leases)
                )
                == 0
            )
            for table in (
                models.offline_authorization_rollouts,
                models.offline_authorization_leases,
            ):
                assert {
                    col["name"] for col in sa.inspect(connection).get_columns(table.name)
                } == set(table.c.keys())
            migration.downgrade()


def test_evidence_blocks_downgrade_before_history_change(workspace, monkeypatch):
    _, grant = _cash_grant(workspace, monkeypatch)
    _, _, factory, _ = workspace
    with factory().get_bind().begin() as connection:
        original = dict(
            connection.execute(sa.select(models.offline_authorization_leases)).mappings().one()
        )
        migration = _migration(connection)
        with pytest.raises(RuntimeError, match="0088 downgrade blocked"):
            migration.downgrade()
        assert (
            dict(
                connection.execute(sa.select(models.offline_authorization_leases)).mappings().one()
            )
            == original
        )
        assert grant["offline_grant"] not in str(original)

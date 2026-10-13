"""Issuer configuration: actual PostgreSQL migration and serialized version-zero writes."""

import base64
import time
from datetime import datetime, timezone
from threading import Event, Thread, current_thread
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models, operations
from restaurant_os.config import get_settings
from restaurant_os.invoicing import emitters
from sqlalchemy.orm import Session
from test_corporate_purchases_postgres import pg_engine as pg_engine
from test_fiscal_authority_postgres import (
    _postgres_alembic,
)
from test_fiscal_authority_postgres import (
    migrated_fiscal_engine as migrated_fiscal_engine,
)
from test_fiscal_emitter_configuration import _configuration
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID


@pytest.fixture
def encryption(monkeypatch):
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        '{"qa":"' + base64.b64encode(bytes(range(32))).decode() + '"}',
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "qa")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_emitter_migration_preserves_legacy_and_blocks_history_downgrade(migrated_fiscal_engine):
    engine, url = migrated_fiscal_engine
    result = _postgres_alembic(url, "upgrade", "0085_fiscal_permissions")
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        org = connection.scalar(sa.text("SELECT id FROM organizations LIMIT 1"))
        connection.execute(
            sa.text(
                "INSERT INTO facturapi_config "
                "(id,organization_id,api_key,organization_rfc,created_at,updated_at) "
                "VALUES ('legacy',:org,'synthetic-private-legacy','SYN010101AAA',now(),now())"
            ),
            {"org": org},
        )
        before = dict(
            connection.execute(sa.text("SELECT * FROM facturapi_config")).mappings().one()
        )
    result = _postgres_alembic(url, "upgrade", "0086_fiscal_emitters")
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        assert (
            dict(connection.execute(sa.text("SELECT * FROM facturapi_config")).mappings().one())
            == before
        )
        assert connection.scalar(sa.text("SELECT COUNT(*) FROM fiscal_emitter_configurations")) == 0
        emitter = connection.scalar(sa.text("SELECT id FROM legal_entities LIMIT 1"))
        connection.execute(
            sa.text(
                "INSERT INTO fiscal_emitter_configurations "
                "VALUES ('qa',:org,:emitter,1,now(),now())"
            ),
            {"org": org, "emitter": emitter},
        )
    result = _postgres_alembic(url, "downgrade", "0085_fiscal_permissions")
    assert result.returncode != 0 and "0086 downgrade blocked" in result.stderr
    with engine.connect() as connection:
        assert (
            connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == "0086_fiscal_emitters"
        )
        assert (
            dict(connection.execute(sa.text("SELECT * FROM facturapi_config")).mappings().one())
            == before
        )


@pytest.mark.parametrize("competing_action", ["create", "revoke"])
def test_issuer_write_waits_on_actual_pg_lock_through_commit(
    pg_engine, encryption, monkeypatch, competing_action
):
    now = datetime.now(timezone.utc)
    actor, role = str(uuid4()), str(uuid4())
    with Session(pg_engine) as session:
        permission = str(uuid4())
        session.execute(
            models.permissions.insert().values(
                id=permission,
                code="invoicing.config.manage",
                description="Synthetic config",
                created_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=ADMIN_ROLE_ID, permission_id=permission)
        )
        session.execute(
            models.roles.insert().values(
                id=role,
                organization_id=operations.ORGANIZATION_ID,
                name="Synthetic issuer manager",
                scope="organization",
                created_at=now,
            )
        )
        session.execute(
            models.users.insert().values(
                id=actor,
                organization_id=operations.ORGANIZATION_ID,
                email="issuer-race@example.invalid",
                display_name="Synthetic",
                status="active",
                authorization_version=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=role, permission_id=permission)
        )
        session.execute(models.user_roles.insert().values(user_id=actor, role_id=role))
        emitter = session.scalar(
            sa.select(models.branches.c.legal_entity_id).where(models.branches.c.id == BRANCH_ID)
        )
        session.execute(
            models.legal_entities.update()
            .where(models.legal_entities.c.id == emitter)
            .values(tax_id="SYN010101AAA")
        )
        session.commit()
    staged, release, started = Event(), Event(), Event()
    results, failures, pids, revoked = [], [], [], []
    original = emitters._audit

    def pause_audit(session, **kwargs):
        if current_thread().name == "issuer-first":
            staged.set()
            assert release.wait(8)
        original(session, **kwargs)

    monkeypatch.setattr(emitters, "_audit", pause_audit)

    def writer(second=False):
        try:
            with Session(pg_engine) as session:
                if second:
                    pids.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                    started.set()
                    if competing_action == "revoke":
                        operations.update_role_permissions(session, role, [], ADMIN_USER_ID)
                        revoked.append(True)
                        return
                results.append(
                    emitters.save_configuration(session, actor, emitter, _configuration())
                )
        except operations.BusinessError as error:
            failures.append(error.code)
        except BaseException as error:
            failures.append(error)

    first = Thread(target=writer, name="issuer-first")
    second = Thread(target=writer, args=(True,), name="issuer-second")
    first.start()
    waiting = False
    try:
        assert staged.wait(8)
        second.start()
        assert started.wait(5)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            with pg_engine.connect() as connection:
                waiting = bool(
                    connection.scalar(
                        sa.text(
                            "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"
                        ),
                        {"pid": pids[0]},
                    )
                )
            if waiting:
                break
            time.sleep(0.02)
    finally:
        release.set()
        first.join(12)
        if second.ident:
            second.join(12)
    assert not first.is_alive() and not second.is_alive()
    assert waiting, "Both writers must contend on an actual PostgreSQL lock"
    assert len(results) == 1
    assert failures == (
        ["fiscal_configuration_version_conflict"] if competing_action == "create" else []
    )
    assert revoked == ([True] if competing_action == "revoke" else [])
    with Session(pg_engine) as session:
        if competing_action == "revoke":
            assert (
                session.scalar(
                    sa.select(models.users.c.authorization_version).where(
                        models.users.c.id == actor
                    )
                )
                == 2
            )
            with pytest.raises(operations.AuthorizationError):
                emitters.save_configuration(
                    session, actor, emitter, _configuration(expected_version=1)
                )
            session.rollback()
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.fiscal_emitter_configurations)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.fiscal_emitter_configuration_versions)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "invoicing.emitter_configuration.updated")
            )
            == 1
        )

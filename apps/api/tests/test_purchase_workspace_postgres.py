"""Isolated PostgreSQL recovery, copy races and actual migration evidence."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.modifier_configuration import (
    copy_modifier_configuration,
    save_modifier_configuration,
)
from restaurant_os.operations import (
    BusinessError,
    create_purchase_document,
    create_purchase_presentation,
    create_supplier,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_platform_api import ADMIN_USER_ID, _seed
from test_purchase_workspace import _presentation, _purchase_payload
from test_workspace_compound_copy import SOURCE, TARGET


@pytest.fixture
def pg_engine():
    url = os.environ.get("SR_WORKSPACE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("SR_WORKSPACE_TEST_POSTGRES_URL is required; configured in CI")
    parsed = make_url(url)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").startswith("sr_workspace_")
        or parsed.query
    ):
        raise RuntimeError("Workspace tests require an isolated local sr_workspace_* database")
    engine = sa.create_engine(
        url, connect_args={"options": "-c statement_timeout=15000 -c lock_timeout=10000"}
    )
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            "0073_pos_catalog_appearance",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    with Session(engine) as session:
        _seed(session)
    try:
        yield engine
    finally:
        engine.dispose()


def _purchase_seed(engine):
    with Session(engine) as session:
        supplier = create_supplier(
            session, {"code": "SR-PG", "commercial_name": "SR fixture"}, ADMIN_USER_ID
        )
        presentation = create_purchase_presentation(
            session, _presentation(supplier["id"]), ADMIN_USER_ID
        )
        return _purchase_payload(supplier["id"], presentation["id"])


def test_pos_catalog_appearance_postgres_default_and_downgrade_guard(pg_engine):
    with Session(pg_engine) as session:
        assert session.scalar(
            sa.select(models.branches.c.pos_catalog_visuals_enabled).limit(1)
        ) is True
        session.execute(
            sa.update(models.branches).values(pos_catalog_visuals_enabled=False)
        )
        session.commit()
    url = os.environ["SR_WORKSPACE_TEST_POSTGRES_URL"]
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "downgrade",
            "0072_purchase_create_commands",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert blocked.returncode != 0
    assert (
        "Cannot downgrade 0073 while hidden catalog visuals are configured"
        in blocked.stdout + blocked.stderr
    )


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_creation_has_one_document_and_no_duplicate_audit(pg_engine, same_key):
    payload = _purchase_seed(pg_engine)
    barrier = Barrier(2)

    def writer(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                result = create_purchase_document(
                    session,
                    payload,
                    ADMIN_USER_ID,
                    "sr-pg-create-" + ("same" if same_key else str(index)),
                )
                return result["id"]
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, range(2)))
    if same_key:
        assert outcomes[0] == outcomes[1]
    else:
        assert outcomes.count("purchase_document_identity_conflict") == 1
    with Session(pg_engine) as session:
        for table, count in (
            (models.purchase_documents, 1),
            (models.purchase_document_lines, 3),
            (models.purchase_create_commands, 1),
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == count
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "purchase.created")
            )
            == 1
        )


def _copy_seed(engine):
    with Session(engine) as session:
        source = dict(
            session.execute(sa.select(models.products).where(models.products.c.id == SOURCE))
            .mappings()
            .one()
        )
        session.execute(
            models.products.insert().values(**{**source, "id": TARGET, "sku": "SR-PG-TARGET"})
        )
        session.commit()
        return save_modifier_configuration(
            session,
            ADMIN_USER_ID,
            SOURCE,
            {
                "expected_version": 0,
                "groups": [
                    {
                        "name": "Preparación",
                        "minimum_selections": 0,
                        "maximum_selections": 1,
                        "options": [
                            {
                                "name": "Sin sal",
                                "effect_type": "instruction",
                                "price_delta_cents": 0,
                            }
                        ],
                    }
                ],
            },
            "sr-pg-source",
        )


def test_concurrent_copy_and_target_writer_have_one_version_winner(pg_engine):
    _copy_seed(pg_engine)
    barrier = Barrier(2)

    def writer(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                if index == 0:
                    copy_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        TARGET,
                        {
                            "source_product_id": SOURCE,
                            "expected_source_version": 1,
                            "expected_target_version": 0,
                        },
                        "sr-pg-copy",
                    )
                else:
                    save_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        TARGET,
                        {"expected_version": 0, "groups": []},
                        "sr-pg-target",
                    )
                return "applied"
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(writer, range(2))) == [
            "applied",
            "modifier_configuration_version_conflict",
        ]
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(models.product_modifier_configurations.c.version).where(
                    models.product_modifier_configurations.c.product_id == TARGET
                )
            )
            == 1
        )


def test_copy_source_change_is_serialized_or_rejected_without_mixture(pg_engine):
    _copy_seed(pg_engine)
    barrier = Barrier(2)

    def writer(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                if index == 0:
                    return copy_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        TARGET,
                        {
                            "source_product_id": SOURCE,
                            "expected_source_version": 1,
                            "expected_target_version": 0,
                        },
                        "sr-pg-copy-source-race",
                    )["groups"]
                save_modifier_configuration(
                    session,
                    ADMIN_USER_ID,
                    SOURCE,
                    {"expected_version": 1, "groups": []},
                    "sr-pg-change-source",
                )
                return "source-applied"
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, range(2)))
    assert outcomes[1] == "source-applied"
    if isinstance(outcomes[0], list):
        assert [group["name"] for group in outcomes[0]] == ["Preparación"]
    else:
        assert outcomes[0] == "modifier_copy_source_version_conflict"
        with Session(pg_engine) as session:
            assert (
                session.scalar(
                    sa.select(sa.func.count())
                    .select_from(models.modifier_groups)
                    .where(models.modifier_groups.c.product_id == TARGET)
                )
                == 0
            )


def test_postgres_migration_history_guard_and_empty_roundtrip(pg_engine):
    url = os.environ["SR_WORKSPACE_TEST_POSTGRES_URL"]
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)

    def migrate(command, revision):
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", command, revision],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )

    assert migrate("downgrade", "0071_classification_rollout").returncode == 0
    assert migrate("upgrade", "0072_purchase_create_commands").returncode == 0
    payload = _purchase_seed(pg_engine)
    with Session(pg_engine) as session:
        create_purchase_document(session, payload, ADMIN_USER_ID, "sr-pg-migration-history")
    blocked = migrate("downgrade", "0071_classification_rollout")
    assert blocked.returncode != 0
    assert (
        "Cannot downgrade 0072 while purchase creation history exists"
        in blocked.stdout + blocked.stderr
    )


def test_reviewed_creation_serializes_with_catalog_writer(pg_engine):
    from restaurant_os.operations import update_purchase_presentation
    from restaurant_os.purchase_workspace import preview_purchase

    payload = _purchase_seed(pg_engine)
    presentation_id = payload["lines"][0]["presentation_id"]
    with Session(pg_engine) as session:
        fingerprint = preview_purchase(session, payload, ADMIN_USER_ID)["context_fingerprint"]
    barrier = Barrier(2)

    def writer(kind):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            if kind == "catalog":
                update_purchase_presentation(
                    session, presentation_id, {"base_unit_yield": "10"}, ADMIN_USER_ID
                )
                return "catalog-updated"
            try:
                purchase = create_purchase_document(
                    session, payload, ADMIN_USER_ID, "sr-reviewed-pg-race", fingerprint
                )
                assert str(purchase["lines"][0]["base_quantity"]) == "10.000000"
                return "created-reviewed"
            except BusinessError as error:
                assert error.code == "purchase_preview_changed"
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, ["catalog", "purchase"]))
    assert outcomes[0] == "catalog-updated"
    with Session(pg_engine) as session:
        expected = 1 if outcomes[1] == "created-reviewed" else 0
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.purchase_documents))
            == expected
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.purchase_create_commands))
            == expected
        )


def test_keyed_creator_races_legacy_identity_without_500(pg_engine):
    payload = _purchase_seed(pg_engine)
    barrier = Barrier(2)

    def writer(key):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return create_purchase_document(session, payload, ADMIN_USER_ID, key)["id"]
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, ["sr-keyed-vs-legacy", None]))
    assert outcomes.count("purchase_document_identity_conflict") == 1
    with Session(pg_engine) as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.purchase_documents)) == 1
        )

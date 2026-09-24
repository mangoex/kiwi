"""Real PostgreSQL race tests; missing disposable URL is a failed gate, never a skip."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.catalog_classification import category_command
from restaurant_os.operations import BusinessError, create_category, update_category
from sqlalchemy.orm import Session
from test_admin_catalog import _seed_admin_catalog_scope
from test_cash_concepts import OWNER_ID, _seed_cash_concept_scope


@pytest.fixture
def engine():
    url = os.environ.get("CATCLASS_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("CATCLASS_TEST_POSTGRES_URL must target a disposable local catclass_* database")
    parsed = sa.engine.make_url(url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").startswith("catclass_")
    ):
        pytest.fail("Refusing nonlocal or non-catclass_* PostgreSQL target")
    schema = "classification_" + uuid4().hex
    owner = sa.create_engine(url, connect_args={"connect_timeout": 5})
    with owner.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    target = sa.create_engine(
        url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5}
    )
    try:
        migration_url = parsed.update_query_dict(
            {"options": f"-csearch_path={schema}", "connect_timeout": "5"}
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "RESTAURANTOS_DATABASE_URL": migration_url.render_as_string(hide_password=False),
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        with target.begin() as connection:
            connection.execute(sa.text("TRUNCATE organizations, permissions CASCADE"))
        with Session(target) as session:
            _seed_cash_concept_scope(session)
            _seed_admin_catalog_scope(session)
            session.commit()
        yield target
    finally:
        target.dispose()
        with owner.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        owner.dispose()


@pytest.mark.parametrize("same_key", [False, True])
def test_postgres_two_sessions_cas_and_idempotency(engine, same_key):
    with Session(engine) as session:
        created = create_category(session, "RACE", actor_user_id=OWNER_ID)
    barrier = Barrier(2)

    def run(index):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                return category_command(
                    session,
                    OWNER_ID,
                    {"classification_code": "food", "expected_version": 1},
                    category_id=created["id"],
                    idempotency_key="same" if same_key else f"key-{index}",
                )
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (1, 2)))
    if same_key:
        assert results[0] == results[1]
    else:
        assert sum(isinstance(result, dict) for result in results) == 1
        assert "category_version_conflict" in results
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(models.product_categories.c.configuration_version).where(
                    models.product_categories.c.id == created["id"]
                )
            )
            == 2
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.category_configuration_commands)
            )
            == 2
        )


def test_postgres_legacy_writer_invalidates_stale_modern_version(engine):
    with Session(engine) as session:
        created = create_category(session, "LEGACY RACE", actor_user_id=OWNER_ID)
    barrier = Barrier(2)

    def run(modern):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            if not modern:
                return update_category(
                    session, created["id"], display_order=3, actor_user_id=OWNER_ID
                )
            try:
                return category_command(
                    session,
                    OWNER_ID,
                    {"classification_code": "drinks", "expected_version": 1},
                    category_id=created["id"],
                    idempotency_key="modern",
                )
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (False, True)))
    with Session(engine) as session:
        row = (
            session.execute(
                sa.select(models.product_categories).where(
                    models.product_categories.c.id == created["id"]
                )
            )
            .mappings()
            .one()
        )
        assert row["display_order"] == 3
        assert row["configuration_version"] == (3 if isinstance(results[1], dict) else 2)
        assert row["classification_code"] == ("drinks" if isinstance(results[1], dict) else None)


def test_postgres_branch_creation_serializes_against_rollout_publication(engine, monkeypatch):
    from restaurant_os import operations
    from restaurant_os.catalog_classification_rollout import rollout_status, transition_rollout
    from test_catalog_classification_rollout import _ack, _classify, _issue, _prepare

    with Session(engine) as session:
        _classify(session)
        prepared = _prepare(session)
        for branch in rollout_status(session, OWNER_ID)["branches"]:
            _ack(session, branch["branch_id"], _issue(session, branch["branch_id"]))
    inserted, release = Event(), Event()
    audit = operations._audit

    def pause_branch(*args, **kwargs):
        audit(*args, **kwargs)
        if kwargs.get("action") == "branch.created":
            inserted.set()
            assert release.wait(timeout=15)

    monkeypatch.setattr(operations, "_audit", pause_branch)

    def create():
        with Session(engine) as session:
            return operations.create_branch(session, "NUEVA", "NEW", actor_user_id=OWNER_ID)

    def publish():
        with Session(engine) as session:
            try:
                return transition_rollout(
                    session,
                    OWNER_ID,
                    {"action": "publish", "expected_version": prepared["version"]},
                    "race-publish",
                )
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        creation = pool.submit(create)
        assert inserted.wait(timeout=15)
        publication = pool.submit(publish)
        try:
            with pytest.raises(TimeoutError):
                publication.result(timeout=0.25)
        finally:
            release.set()
        assert creation.result(timeout=15)["code"] == "NEW"
        assert publication.result(timeout=15) == "classification_rollout_incomplete"
    with Session(engine) as session:
        assert rollout_status(session, OWNER_ID)["state"] == "preparing"


def test_postgres_migration_roundtrip_preserves_catalog_and_rejects_history(engine):
    with engine.connect() as connection:
        schema = connection.scalar(sa.text("SELECT current_schema()"))
        columns = "id, organization_id, name, display_order, status, created_at, updated_at"
        before = connection.execute(
            sa.text(f"SELECT {columns} FROM product_categories ORDER BY id")
        ).all()
        products = connection.execute(sa.text("SELECT * FROM products ORDER BY id")).all()
    url = engine.url.update_query_dict(
        {"options": f"-csearch_path={schema}", "connect_timeout": "5"}
    )

    def migrate(action, revision):
        return subprocess.run(
            [sys.executable, "-m", "alembic", action, revision],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "RESTAURANTOS_DATABASE_URL": url.render_as_string(hide_password=False),
            },
            capture_output=True,
            text=True,
            timeout=120,
        )

    result = migrate("downgrade", "0069_selectable_compound_product")
    assert result.returncode == 0, result.stderr
    result = migrate("upgrade", "0070_catalog_classification")
    assert result.returncode == 0, result.stderr
    result = migrate("upgrade", "0071_classification_rollout")
    assert result.returncode == 0, result.stderr
    with engine.connect() as connection:
        assert (
            connection.execute(
                sa.text(f"SELECT {columns} FROM product_categories ORDER BY id")
            ).all()
            == before
        )
        assert connection.execute(sa.text("SELECT * FROM products ORDER BY id")).all() == products
        assert (
            connection.scalar(
                sa.text(
                    "SELECT count(*) FROM product_categories WHERE "
                    "classification_code IS NOT NULL OR configuration_version <> 1"
                )
            )
            == 0
        )
    with Session(engine) as session:
        create_category(session, "PROTECTED HISTORY", actor_user_id=OWNER_ID)
    result = migrate("downgrade", "0069_selectable_compound_product")
    assert result.returncode != 0
    assert "Classification history exists" in result.stderr
    with engine.connect() as connection:
        assert (
            connection.scalar(sa.text("SELECT count(*) FROM category_configuration_commands")) == 1
        )

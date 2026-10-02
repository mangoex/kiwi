# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-pos-cashier-postgres-v1
"""Run the amended cashier journey in an isolated PostgreSQL schema."""
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from test_platform_api import _seed
from test_pos_cashier_workflow import (
    _assert_amended_order_ready,
    _assert_historical_source_reordered,
)


def _validated_test_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    assert not url.query, 'Connection query overrides are forbidden for this isolated fixture'
    assert url.get_backend_name() == 'postgresql'
    assert url.host in {'127.0.0.1', 'localhost'}
    assert url.database == 'pos_cashier_ci' or (url.database or '').startswith('kiwi_cashier_test_')
    return url


@pytest.mark.parametrize('raw_url', [
    'postgresql+psycopg://qa@127.0.0.1/pos_cashier_ci?host=remote.invalid',
    'postgresql+psycopg://qa@127.0.0.1/pos_cashier_ci?dbname=production',
    'postgresql+psycopg://qa@remote.invalid/pos_cashier_ci',
    'postgresql+psycopg://qa@127.0.0.1/production',
])
def test_cashier_postgres_fixture_rejects_destination_overrides(raw_url: str) -> None:
    with pytest.raises(AssertionError):
        _validated_test_url(raw_url)


@pytest.mark.parametrize('journey', ['ready', 'delete_previous', 'reorder'])
def test_cashier_amended_journey_postgres(journey: str) -> None:
    raw_url = os.getenv('POS_CASHIER_TEST_POSTGRES_URL')
    if not raw_url:
        pytest.skip('POS_CASHIER_TEST_POSTGRES_URL requires an isolated test database')
    url = _validated_test_url(raw_url)
    schema = 'cashier_qa_' + uuid4().hex
    engine = sa.create_engine(url)
    scoped_engine = sa.create_engine(
        url, connect_args={'options': f'-csearch_path={schema} -cstatement_timeout=15000'},
    )
    try:
        with engine.begin() as connection:
            connection.execute(sa.schema.CreateSchema(schema))
        migration_url = url.update_query_dict({'options': f'-csearch_path={schema}'})
        migration_env = {
            **os.environ,
            'RESTAURANTOS_DATABASE_URL': migration_url.render_as_string(hide_password=False),
        }
        migration_env.pop('DATABASE_URL', None)
        migrated = subprocess.run(
            [sys.executable, '-m', 'alembic', '-c', 'alembic.ini', 'upgrade', 'head'],
            cwd=Path(__file__).resolve().parents[1], env=migration_env,
            capture_output=True, text=True, timeout=120,
        )
        assert migrated.returncode == 0, migrated.stderr
        with scoped_engine.begin() as connection:
            names = sa.inspect(connection).get_table_names(schema=schema)
            quoted = ', '.join(
                connection.dialect.identifier_preparer.quote(schema) + '.'
                + connection.dialect.identifier_preparer.quote(name)
                for name in names if name != 'alembic_version'
            )
            connection.execute(sa.text('TRUNCATE TABLE ' + quoted + ' RESTART IDENTITY CASCADE'))
        factory = sessionmaker(bind=scoped_engine, expire_on_commit=False)
        with factory() as session:
            _seed(session)
        app = create_app()
        app.state.test_session_factory = factory

        def scoped_session() -> Generator[Session, None, None]:
            with factory() as session:
                yield session

        app.dependency_overrides[get_session] = scoped_session
        client = TestClient(app)
        try:
            if journey == 'ready':
                _assert_amended_order_ready(client)
            else:
                # Canonical PostgreSQL stores VARCHAR(500); SQLite can retain oversized legacy text.
                _assert_historical_source_reordered(client, journey, note_length=500)
        finally:
            client.close()
    finally:
        scoped_engine.dispose()
        with engine.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()

"""Run the administrative scope contracts against an isolated PostgreSQL database."""

import os

import pytest
import sqlalchemy as sa
import test_admin_unification as contracts
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from test_platform_api import _seed


@pytest.fixture
def pg_contracts(monkeypatch):
    url = os.environ.get("ADMIN_UNIFICATION_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ADMIN_UNIFICATION_TEST_POSTGRES_URL is required; configured in CI")
    parsed = make_url(url)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"127.0.0.1", "localhost"}
        or parsed.database != "admin_unification_test_ci"
        or parsed.query
    ):
        raise RuntimeError("Use only the isolated local admin_unification_test_ci database")
    engine = sa.create_engine(url)
    # No production URL or fallback: this fixture owns only the explicit disposable test database.
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        _seed(db)
    app = create_app()

    def session_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_session] = session_override
    app.state.test_session_factory = factory
    client = TestClient(app)
    monkeypatch.setattr(contracts, "_client_with_seeded_database", lambda: client)
    try:
        yield
    finally:
        client.close()
        engine.dispose()


CASES = [
    (
        "test_partial_inventory_permissions_reject_without_server_error",
        ("inventory.waste", "/inventory/wastes"),
    ),
    (
        "test_partial_inventory_permissions_reject_without_server_error",
        ("inventory.transfer.send", "/inventory/transfers"),
    ),
    *[
        (name, ())
        for name in (
            "test_session_projects_compatible_capabilities_without_new_grants",
            "test_read_only_purchase_account_cannot_preview_write",
            "test_explicit_availability_branch_does_not_modify_other_branch",
            "test_production_recipes_use_the_requested_authorized_branch",
            "test_transfer_destinations_do_not_require_corporate_administration",
            "test_recipe_default_scope_does_not_expand_a_mixed_account",
            "test_session_branch_directory_is_limited_to_allowed_scope",
        )
    ],
]


@pytest.mark.parametrize("contract,arguments", CASES)
def test_admin_scope_contract_on_postgres(pg_contracts, contract, arguments):
    getattr(contracts, contract)(*arguments)

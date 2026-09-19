"""SQLite bundle capture/hydration regressions for ORD-OFF001."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from edge_gateway.order_outbox import OrderOutbox
from restaurant_os import models
from restaurant_os.offline_order_catalog import (
    build_catalog_snapshot,
    build_operational_seed,
    hydrate_bundle,
    hydrate_catalog_snapshot,
    refresh_catalog_snapshot,
)
from restaurant_os.operations import BusinessError, create_local_order
from restaurant_os.order_execution import order_execution_context
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_cash_concepts import ORG_ID
from test_cash_ledger import BRANCH_A, NOW, _new_session
from test_combo_compositions import ACTOR, BURGER, COMBO
from test_domain_offline_orders import _context, _seed_combo_order_scope

BUNDLE_HASH = "b" * 64


def _bundle_source() -> tuple[sa.Engine, Session, dict[str, object], dict[str, object]]:
    engine, session = _new_session()
    _seed_combo_order_scope(session)
    session.execute(
        models.price_versions.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000009399",
            organization_id=ORG_ID,
            product_id=BURGER,
            price_cents=5_000,
            currency="MXN",
            valid_from=NOW,
            valid_to=None,
            created_at=NOW,
        )
    )
    session.commit()
    return (
        engine,
        session,
        build_catalog_snapshot(session, organization_id=ORG_ID, branch_id=BRANCH_A),
        build_operational_seed(
            session,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            actor_ids=[ACTOR],
        ),
    )


def _manifest(bundle_hash: str = BUNDLE_HASH) -> dict[str, str]:
    return {
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "bundle_hash": bundle_hash,
    }


def _sqlite_engine() -> sa.Engine:
    engine = create_engine("sqlite+pysqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def test_bundle_hydrates_exact_catalog_and_replays_domain_against_frozen_values() -> None:
    source_engine, operational, catalog, seed = _bundle_source()
    catalog_engine = _sqlite_engine()
    catalog_session = None
    try:
        catalog_session = hydrate_catalog_snapshot(
            catalog_engine,
            manifest=_manifest(),
            catalog=catalog,
            operational_seed=seed,
        )
        assert catalog["tables"]["recipe_components"][0]["gross_quantity"] == "0.250000"
        assert catalog["tables"]["recipes"][0]["valid_from"].endswith("Z")
        assert "user_credentials" not in catalog["tables"]
        assert "password" not in repr(seed).lower()

        operational.execute(
            models.price_versions.update()
            .where(
                models.price_versions.c.product_id == COMBO,
                models.price_versions.c.valid_to.is_(None),
            )
            .values(price_cents=999)
        )
        operational.execute(
            models.inventory_cost_states.update()
            .where(
                models.inventory_cost_states.c.branch_id == BRANCH_A,
                models.inventory_cost_states.c.item_id == "018f6f73-2d0a-74f0-8f1c-000000009307",
            )
            .values(average_unit_cost=Decimal("99"))
        )
        with order_execution_context(_context(catalog_session=catalog_session)):
            order = create_local_order(
                operational,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="offline-catalog-snapshot-order",
                commit=False,
            )
        assert order["total_cents"] == 15_900
        assert Decimal(str(order["consumption_snapshots"][0]["total_theoretical_cost"])) == Decimal(
            "5.000000"
        )
        operational.rollback()

        with pytest.raises(OperationalError):
            catalog_session.execute(
                models.price_versions.update()
                .where(models.price_versions.c.product_id == COMBO)
                .values(price_cents=1)
            )
        catalog_session.rollback()
    finally:
        if catalog_session is not None:
            catalog_session.close()
        catalog_engine.dispose()
        operational.close()
        source_engine.dispose()


def test_hydration_is_atomic_and_restart_only_accepts_the_same_hash() -> None:
    source_engine, source, catalog, seed = _bundle_source()
    catalog_engine = _sqlite_engine()
    hydrated = None
    try:
        catalog["tables"]["recipe_components"][0]["item_id"] = "outside-the-bundle"
        with pytest.raises(BusinessError, match="foreign key"):
            hydrate_catalog_snapshot(
                catalog_engine,
                manifest=_manifest(),
                catalog=catalog,
                operational_seed=seed,
            )
        assert not sa.inspect(catalog_engine).has_table("offline_order_catalog_installations")

        # Rebuild after the rejected payload so the second attempt exercises an
        # actual durable installation and the same-hash restart path.
        catalog = build_catalog_snapshot(source, organization_id=ORG_ID, branch_id=BRANCH_A)
        hydrated = hydrate_catalog_snapshot(
            catalog_engine,
            manifest=_manifest(),
            catalog=catalog,
            operational_seed=seed,
        )
        hydrated.close()
        hydrated = hydrate_catalog_snapshot(
            catalog_engine,
            manifest=_manifest(),
            catalog=catalog,
            operational_seed=seed,
        )
        assert hydrated.scalar(sa.select(models.price_versions.c.price_cents)) == 15_900
        hydrated.close()
        hydrated = None
        with pytest.raises(BusinessError, match="different bundle"):
            hydrate_catalog_snapshot(
                catalog_engine,
                manifest=_manifest("c" * 64),
                catalog=catalog,
                operational_seed=seed,
            )
    finally:
        if hydrated is not None:
            hydrated.close()
        catalog_engine.dispose()
        source.close()
        source_engine.dispose()


def test_public_hydrator_keeps_operational_database_writable_and_catalog_read_only(
    tmp_path: Path,
) -> None:
    source_engine, source, catalog, seed = _bundle_source()
    operational_outbox = OrderOutbox(tmp_path / "operational.db")
    catalog_outbox = OrderOutbox(tmp_path / "catalog.db")
    operational_engine = operational_outbox.engine
    catalog_engine = catalog_outbox.engine
    try:
        bundle = {"manifest": _manifest(), "catalog": catalog, "operational_seed": seed}
        assert hydrate_bundle(operational_engine, bundle, include_operational_seed=True) == {
            "branch_id": BRANCH_A,
            "bundle_hash": BUNDLE_HASH,
        }
        with Session(operational_engine) as operational:
            assert operational.scalar(sa.text("PRAGMA query_only")) == 0
            assert operational.scalar(sa.select(sa.func.count()).select_from(models.products)) == 3

        hydrate_bundle(catalog_engine, bundle, include_operational_seed=False)
        with Session(catalog_engine) as frozen:
            assert frozen.scalar(sa.text("PRAGMA query_only")) == 1
            with Session(operational_engine) as operational:
                with order_execution_context(_context(catalog_session=frozen)):
                    order = create_local_order(
                        operational,
                        [{"product_id": COMBO, "quantity": 1}],
                        register_id="CAJA-01",
                        actor_user_id=ACTOR,
                        idempotency_key="offline-hydrated-order",
                        commit=False,
                    )
                assert order["total_cents"] == 15_900
                assert (
                    operational.scalar(
                        sa.select(sa.func.count()).select_from(models.production_tasks)
                    )
                    == 2
                )
                operational.rollback()
            with pytest.raises(OperationalError):
                frozen.execute(models.products.update().values(name="forbidden"))
    finally:
        catalog_engine.dispose()
        operational_engine.dispose()
        source.close()
        source_engine.dispose()


def test_refresh_replaces_seeded_authorization_links_without_rewriting_history() -> None:
    source_engine, source, catalog, seed = _bundle_source()
    operational_engine = _sqlite_engine()
    omitted_actor = "018f6f73-2d0a-74f0-8f1c-000000009497"
    try:
        role_id = seed["tables"]["roles"][0]["id"]
        source.execute(
            models.users.insert().values(
                id=omitted_actor,
                organization_id=ORG_ID,
                email="removed-offline-actor@example.invalid",
                display_name="Removed offline actor",
                employee_code=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        source.execute(
            models.user_roles.insert().values(
                user_id=omitted_actor, role_id=role_id, branch_id=BRANCH_A
            )
        )
        source.commit()
        seed = build_operational_seed(
            source,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            actor_ids=[ACTOR, omitted_actor],
        )
        bundle = {"manifest": _manifest(), "catalog": catalog, "operational_seed": seed}
        hydrate_bundle(operational_engine, bundle, include_operational_seed=True)
        with Session(operational_engine) as operational:
            role_ids = {row["id"] for row in seed["tables"]["roles"]}
            assert (
                operational.scalar(
                    sa.select(sa.func.count())
                    .select_from(models.role_permissions)
                    .where(models.role_permissions.c.role_id.in_(role_ids))
                )
                > 0
            )
            operational.execute(
                models.audit_events.insert().values(
                    id="018f6f73-2d0a-74f0-8f1c-000000009499",
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    actor_user_id=ACTOR,
                    action="offline.order.accepted",
                    entity_type="order",
                    entity_id="018f6f73-2d0a-74f0-8f1c-000000009498",
                    payload={"immutable": True},
                    correlation_id=None,
                    created_at=NOW,
                )
            )
            operational.commit()

        refreshed_catalog = deepcopy(catalog)
        refreshed_catalog["tables"]["products"][0]["name"] = "Producto renovado"
        refreshed_seed = deepcopy(seed)
        refreshed_seed["tables"]["role_permissions"] = []
        refreshed_seed["tables"]["role_authority_grants"] = []
        refreshed_seed["tables"]["user_roles"] = []
        # A renewed grant can omit an actor completely. Its identity stays in
        # the operational history, but its previous local authority must go.
        refreshed_seed["tables"]["users"] = [
            row for row in refreshed_seed["tables"]["users"] if row["id"] != omitted_actor
        ]
        refreshed_seed["tables"]["employee_code_registry"] = [
            row
            for row in refreshed_seed["tables"]["employee_code_registry"]
            if row["subject_id"] != omitted_actor
        ]
        refreshed_seed["tables"]["cash_shifts"] = [
            row
            for row in refreshed_seed["tables"]["cash_shifts"]
            if row["cashier_user_id"] != omitted_actor
        ]
        refresh_catalog_snapshot(
            operational_engine,
            manifest=_manifest("c" * 64),
            catalog=refreshed_catalog,
            operational_seed=refreshed_seed,
        )

        with Session(operational_engine) as operational:
            assert (
                operational.scalar(
                    sa.select(sa.func.count())
                    .select_from(models.role_permissions)
                    .where(models.role_permissions.c.role_id.in_(role_ids))
                )
                == 0
            )
            assert operational.scalar(
                sa.select(models.users.c.id).where(models.users.c.id == omitted_actor)
            ) == omitted_actor
            assert (
                operational.scalar(
                    sa.select(sa.func.count())
                    .select_from(models.user_roles)
                    .where(
                        models.user_roles.c.user_id == omitted_actor,
                        sa.or_(
                            models.user_roles.c.branch_id.is_(None),
                            models.user_roles.c.branch_id == BRANCH_A,
                        ),
                    )
                )
                == 0
            )
            assert operational.scalar(
                sa.select(models.audit_events.c.payload).where(
                    models.audit_events.c.id == "018f6f73-2d0a-74f0-8f1c-000000009499"
                )
            ) == {"immutable": True}
            assert (
                operational.scalar(
                    sa.select(models.products.c.name).where(
                        models.products.c.id == refreshed_catalog["tables"]["products"][0]["id"]
                    )
                )
                == "Producto renovado"
            )
    finally:
        operational_engine.dispose()
        source.close()
        source_engine.dispose()

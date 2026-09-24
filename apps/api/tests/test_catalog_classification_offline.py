from copy import deepcopy

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.offline_order_catalog import (
    build_catalog_snapshot,
    get_installed_classification_mode,
    hydrate_catalog_snapshot,
    refresh_catalog_snapshot,
)
from restaurant_os.operations import BusinessError
from sqlalchemy.orm import Session
from test_cash_concepts import ORG_ID
from test_cash_ledger import BRANCH_A, NOW
from test_offline_order_catalog import _bundle_source, _manifest


def test_v3_generation_survives_restart_and_rejects_rollback(tmp_path):
    source_engine, source, _, seed = _bundle_source()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'local.db'}")
    try:
        catalog = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, catalog_schema="ord-off-catalog/v3"
        )
        manifest = {**_manifest(), "catalog_generation": 2, "catalog_classification_mode": "legacy"}
        hydrate_catalog_snapshot(
            engine,
            manifest=manifest,
            catalog=catalog,
            operational_seed=seed,
            read_only=False,
            full_operational_schema=True,
        ).close()
        engine.dispose()
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'local.db'}")
        for candidate in [
            dict(manifest, catalog_generation=1),
            dict(manifest, bundle_hash="a" * 64),
            dict(manifest, catalog_classification_mode="explicit"),
        ]:
            with pytest.raises(BusinessError):
                refresh_catalog_snapshot(
                    engine, manifest=candidate, catalog=catalog, operational_seed=seed
                )
        refresh_catalog_snapshot(engine, manifest=manifest, catalog=catalog, operational_seed=seed)
        rollback = dict(manifest, catalog_generation=3, bundle_hash="c" * 64)
        refresh_catalog_snapshot(engine, manifest=rollback, catalog=catalog, operational_seed=seed)
        legacy = build_catalog_snapshot(source, organization_id=ORG_ID, branch_id=BRANCH_A)
        with pytest.raises(BusinessError):
            refresh_catalog_snapshot(
                engine, manifest=_manifest(), catalog=legacy, operational_seed=seed
            )
    finally:
        source.close()
        source_engine.dispose()
        engine.dispose()


def test_v3_hierarchy_is_scoped_and_hydrates_with_foreign_keys():
    source_engine, source, _, seed = _bundle_source()
    target = sa.create_engine("sqlite://")
    try:
        category_id, product_id = source.execute(
            sa.select(models.products.c.category_id, models.products.c.id)
        ).first()
        source.execute(models.product_categories.update().values(classification_code="drinks"))
        source.execute(
            models.category_option_groups.insert().values(
                id="group",
                organization_id=ORG_ID,
                category_id=category_id,
                code="BEER",
                name="Beer",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        source.execute(
            models.category_option_values.insert().values(
                id="value",
                group_id="group",
                code="IPA",
                name="Artisanal",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        source.execute(
            models.product_option_value_assignments.insert().values(
                id="assignment",
                product_id=product_id,
                group_id="group",
                option_value_id="value",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        source.commit()
        catalog = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, catalog_schema="ord-off-catalog/v3"
        )
        assert catalog["tables"]["product_option_value_assignments"][0]["product_id"] == product_id
        manifest = {
            **_manifest(),
            "catalog_generation": 1,
            "catalog_classification_mode": "explicit",
        }
        with target.connect() as connection:
            connection.execute(sa.text("PRAGMA foreign_keys=ON"))
        hydrated = hydrate_catalog_snapshot(
            target, manifest=manifest, catalog=catalog, operational_seed=seed, read_only=False
        )
        assert get_installed_classification_mode(hydrated, BRANCH_A) == "explicit"
        assert hydrated.scalar(sa.select(models.category_option_values.c.name)) == "Artisanal"
        assert (
            hydrated.scalar(sa.select(models.product_option_value_assignments.c.product_id))
            == product_id
        )
        hydrated.close()
        invalid = deepcopy(catalog)
        invalid["tables"]["category_option_groups"][0]["organization_id"] = "other-organization"
        with pytest.raises(BusinessError):
            refresh_catalog_snapshot(
                target,
                manifest=dict(manifest, catalog_generation=2),
                catalog=invalid,
                operational_seed=seed,
            )
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()


def test_failed_refresh_rolls_back_generation_and_catalog(monkeypatch):
    import restaurant_os.offline_order_catalog as module

    source_engine, source, _, seed = _bundle_source()
    target = sa.create_engine("sqlite://")
    try:
        source.execute(models.product_categories.update().values(classification_code="food"))
        source.commit()
        catalog = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, catalog_schema="ord-off-catalog/v3"
        )
        manifest = {
            **_manifest(),
            "catalog_generation": 1,
            "catalog_classification_mode": "explicit",
        }
        hydrate_catalog_snapshot(
            target,
            manifest=manifest,
            catalog=catalog,
            operational_seed=seed,
            read_only=False,
            full_operational_schema=True,
        ).close()
        candidate = deepcopy(catalog)
        candidate["tables"]["product_categories"][0]["classification_code"] = "drinks"
        original = module._store_generation

        def fail(session, incoming):
            original(session, incoming)
            raise RuntimeError("injected transaction failure")

        with monkeypatch.context() as fault:
            fault.setattr(module, "_store_generation", fail)
            with pytest.raises(RuntimeError, match="injected"):
                refresh_catalog_snapshot(
                    target,
                    manifest=dict(manifest, catalog_generation=2, bundle_hash="d" * 64),
                    catalog=candidate,
                    operational_seed=seed,
                )
        with Session(target) as session:
            assert (
                session.scalar(sa.select(models.product_categories.c.classification_code)) == "food"
            )
            assert (
                session.scalar(
                    sa.text("SELECT catalog_generation FROM offline_order_catalog_generations")
                )
                == 1
            )
        refresh_catalog_snapshot(
            target,
            manifest=dict(manifest, catalog_generation=2, bundle_hash="d" * 64),
            catalog=candidate,
            operational_seed=seed,
        )
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()


@pytest.mark.parametrize(
    "generation,mode", [(0, "legacy"), (True, "legacy"), (1, "invalid"), (None, "explicit")]
)
def test_invalid_generation_never_changes_target(generation, mode):
    source_engine, source, _, seed = _bundle_source()
    target = sa.create_engine("sqlite://")
    try:
        catalog = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, catalog_schema="ord-off-catalog/v3"
        )
        with pytest.raises(BusinessError):
            hydrate_catalog_snapshot(
                target,
                manifest={
                    **_manifest(),
                    "catalog_generation": generation,
                    "catalog_classification_mode": mode,
                },
                catalog=catalog,
                operational_seed=seed,
            )
        assert not sa.inspect(target).has_table("products")
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()


@pytest.mark.parametrize("schema", ["ord-off-catalog/v1", "ord-off-catalog/v2"])
def test_old_signed_catalog_bootstrap_retains_legacy_navigation(schema):
    source_engine, source, catalog, seed = _bundle_source()
    target = sa.create_engine("sqlite://")
    try:
        catalog["schema_version"] = schema
        hydrated = hydrate_catalog_snapshot(
            target, manifest=_manifest(), catalog=catalog, operational_seed=seed, read_only=False
        )
        assert get_installed_classification_mode(hydrated, BRANCH_A) == "legacy"
        assert hydrated.scalar(sa.select(models.product_categories.c.classification_code)) is None
        hydrated.close()
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()


def test_v3_explicit_missing_classification_rejected_before_install():
    source_engine, source, _, seed = _bundle_source()
    target = sa.create_engine("sqlite://")
    try:
        catalog = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, catalog_schema="ord-off-catalog/v3"
        )
        with pytest.raises(BusinessError, match="unclassified"):
            hydrate_catalog_snapshot(
                target,
                manifest={
                    **_manifest(),
                    "catalog_generation": 1,
                    "catalog_classification_mode": "explicit",
                },
                catalog=catalog,
                operational_seed=seed,
            )
        assert not sa.inspect(target).has_table("products")
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()


def test_legacy_sqlite_table_expands_additively_before_v3_install():
    source_engine, source, catalog, seed = _bundle_source()
    target = sa.create_engine("sqlite://")
    try:
        with target.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TABLE product_categories (id VARCHAR(36) PRIMARY KEY, "
                    "organization_id VARCHAR(36) NOT NULL, name VARCHAR(120) NOT NULL, "
                    "display_order INTEGER NOT NULL DEFAULT 0, "
                    "status VARCHAR(32) NOT NULL DEFAULT 'active', "
                    "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
                )
            )
        hydrated = hydrate_catalog_snapshot(
            target,
            manifest=_manifest(),
            catalog=catalog,
            operational_seed=seed,
            read_only=False,
            full_operational_schema=True,
        )
        previous_ids = set(hydrated.scalars(sa.select(models.product_categories.c.id)))
        hydrated.close()
        source.execute(models.product_categories.update().values(classification_code="food"))
        source.commit()
        v3 = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, catalog_schema="ord-off-catalog/v3"
        )
        refresh_catalog_snapshot(
            target,
            manifest={
                **_manifest("e" * 64),
                "catalog_generation": 1,
                "catalog_classification_mode": "explicit",
            },
            catalog=v3,
            operational_seed=seed,
        )
        with Session(target) as session:
            assert set(session.scalars(sa.select(models.product_categories.c.id))) == previous_ids
            assert get_installed_classification_mode(session, BRANCH_A) == "explicit"
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()

"""Regression coverage for append-only canonical recipe publication."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from restaurant_os import models, recipe_catalog_seed
from restaurant_os.recipe_catalog_seed import (
    MANIFEST_PATH,
    MANIFEST_SHA256,
    ORGANIZATION_ID,
    PENDING_ITEM_SKUS,
    PENDING_RECIPE_SKUS,
    PRESERVED_SKU,
    PRODUCTION_SCHEMA_HEAD,
    RecipeCatalogSeedError,
    _load_manifest,
    _require_reviewed_schema_head,
    apply_seed_plan,
    build_seed_plan,
    main,
    publish_recipe_catalog,
)
from sqlalchemy.orm import Session


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_scope(session: Session, *, with_history: bool) -> None:
    now = _now()
    session.execute(
        models.organizations.insert().values(
            id=ORGANIZATION_ID, name="Test org", status="active", created_at=now, updated_at=now
        )
    )
    session.execute(
        models.users.insert().values(
            id="actor-history",
            organization_id=ORGANIZATION_ID,
            email="history@example.test",
            display_name="History",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.roles.insert().values(
            id="role-recipe-publisher",
            organization_id=ORGANIZATION_ID,
            name="Recipe publisher",
            scope="organization",
            created_at=now,
        )
    )
    session.execute(
        models.permissions.insert().values(
            id="permission-recipes-manage",
            code="recipes.manage",
            description="Manage recipes",
            created_at=now,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id="actor-history", role_id="role-recipe-publisher", branch_id=None
        )
    )
    session.execute(
        models.role_permissions.insert().values(
            role_id="role-recipe-publisher", permission_id="permission-recipes-manage"
        )
    )
    session.execute(
        models.role_authority_grants.insert().values(
            role_id="role-recipe-publisher",
            authority_kind="organization_all_permissions",
            created_at=now,
        )
    )
    for code, name, dimension, precision in (
        ("KG", "Kilo", "mass", 6),
        ("L", "Litro", "volume", 6),
        ("PZ", "Pieza", "discrete", 0),
    ):
        session.execute(
            models.inventory_units.insert().values(
                id=f"unit-{code}",
                organization_id=ORGANIZATION_ID,
                code=code,
                name=name,
                dimension=dimension,
                precision_scale=precision,
                created_at=now,
            )
        )
    recipes, _ = _load_manifest()
    categories = {recipe["group"] for recipe in recipes} | {"CAFE Y MACCHA"}
    for index, category in enumerate(sorted(categories), start=1):
        session.execute(
            models.product_categories.insert().values(
                id=f"cat-{index}",
                organization_id=ORGANIZATION_ID,
                name=category,
                display_order=index,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
    session.execute(
        models.product_categories.update()
        .where(models.product_categories.c.name == "CAFE Y MACCHA")
        .values(name="Café y Matcha", status="archived", display_order=2)
    )
    session.execute(
        models.product_categories.update()
        .where(models.product_categories.c.name == "BEBIDAS")
        .values(status="active", display_order=20)
    )
    category_ids = dict(
        session.execute(
            sa.select(models.product_categories.c.name, models.product_categories.c.id)
        ).all()
    )
    for recipe in recipes:
        session.execute(
            models.products.insert().values(
                id=f"prod-{recipe['sku']}",
                organization_id=ORGANIZATION_ID,
                category_id=category_ids[recipe["group"]],
                name=recipe["name"],
                sku=recipe["sku"],
                description=None,
                station="test",
                status="active",
                catalog_scope="organization",
                source_branch_id=None,
                created_at=now,
                updated_at=now,
            )
        )
    items = {
        component["sku"]: component for recipe in recipes for component in recipe["components"]
    }
    for sku, component in items.items():
        unit = {"KILO": "unit-KG", "LITRO": "unit-L", "PZA": "unit-PZ"}[component["unit"]]
        session.execute(
            models.inventory_items.insert().values(
                id=f"item-{sku}",
                organization_id=ORGANIZATION_ID,
                name=component["name"],
                sku=sku,
                base_unit_id=unit,
                item_type="ingredient",
                category_name="TEST",
                catalog_scope="organization",
                source_branch_id=None,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
    if not with_history:
        session.flush()
        return
    product_id = "prod-06002"
    history_items = [f"item-HISTORICO-{index}" for index in range(1, 12)]
    for index, item_id in enumerate(history_items, start=1):
        session.execute(
            models.inventory_items.insert().values(
                id=item_id,
                organization_id=ORGANIZATION_ID,
                name=f"HISTORICO {index}",
                sku=f"HISTORICO-{index}",
                base_unit_id="unit-PZ",
                item_type="ingredient",
                category_name="TEST",
                catalog_scope="organization",
                source_branch_id=None,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
    for version in range(1, 5):
        recipe_id = f"recipe-06002-v{version}"
        session.execute(
            models.recipes.insert().values(
                id=recipe_id,
                organization_id=ORGANIZATION_ID,
                product_id=product_id,
                output_item_id=None,
                branch_id=None,
                recipe_type="sale",
                version=version,
                status="active" if version == 4 else "inactive",
                yield_quantity=Decimal("1"),
                yield_unit_id="unit-PZ",
                valid_from=now,
                valid_to=None,
                created_at=now,
                updated_at=now,
            )
        )
        for index, item_id in enumerate(history_items[: 11 if version == 4 else 1], start=1):
            session.execute(
                models.recipe_components.insert().values(
                    recipe_id=recipe_id,
                    item_id=item_id,
                    quantity_base_units=Decimal("1"),
                    unit_id="unit-PZ",
                    net_quantity=Decimal("1"),
                    waste_rate=Decimal("0"),
                    gross_quantity=Decimal("1"),
                    sort_order=index,
                    notes=None,
                )
            )
        session.execute(
            models.recipe_version_commands.insert().values(
                id=f"command-06002-v{version}",
                organization_id=ORGANIZATION_ID,
                actor_user_id="actor-history",
                product_id=product_id,
                branch_id=None,
                recipe_id=recipe_id,
                idempotency_key=f"history-{version}",
                request_hash="a" * 64,
                result={},
                created_at=now,
            )
        )
    session.flush()


def _session() -> Session:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    models.metadata.create_all(engine)
    return Session(engine)


def test_manifest_has_exact_historical_counts_without_pdf_or_xls() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=False)
        plan = build_seed_plan(session)
        report = plan.report(applied=False)
        assert report["manifest_recipes"] == 329
        assert report["skipped_modifiers"] == 14
        assert report["manifest_candidate_recipes"] == 315
        assert report["publishable_recipes"] == 307
        assert report["components_to_seed"] == 1395
        assert report["products_to_create"] == []
        assert report["items_to_create"] == []
        assert report["pending_recipe_skus"] == sorted(PENDING_RECIPE_SKUS)
        assert report["pending_item_skus"] == sorted(PENDING_ITEM_SKUS)
    finally:
        session.close()


def test_empty_catalog_fails_closed_instead_of_inventing_307_products() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=False)
        session.execute(models.products.delete())
        session.execute(models.inventory_items.delete())
        with pytest.raises(RecipeCatalogSeedError, match="unexpected missing active products"):
            build_seed_plan(session)
    finally:
        session.close()


def test_dry_run_keeps_pending_products_out_of_catalog_and_menu() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=False)
        report = build_seed_plan(session).report(applied=False)
        assert report["categories_to_create"] == []
        apply_seed_plan(session, build_seed_plan(session))
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.products).where(
                models.products.c.sku.in_(PENDING_RECIPE_SKUS)
            )
        ).scalar_one() == 0
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.inventory_items).where(
                models.inventory_items.c.sku.in_(PENDING_ITEM_SKUS)
            )
        ).scalar_one() == 0
        assert (
            session.execute(
                sa.select(models.product_categories.c.status).where(
                    models.product_categories.c.name == "Café y Matcha"
                )
            ).scalar_one()
            == "archived"
        )
        assert (
            session.execute(
                sa.select(models.product_categories.c.status).where(
                    models.product_categories.c.name == "BEBIDAS"
                )
            ).scalar_one()
            == "active"
        )
        replay = build_seed_plan(session).report(applied=False)
        assert replay["categories_to_create"] == []
    finally:
        session.close()


def test_dry_run_rejects_a_preexisting_pending_product() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=False)
        now = _now()
        session.execute(
            models.products.insert().values(
                id="pending-product",
                organization_id=ORGANIZATION_ID,
                category_id="cat-1",
                name="CAFE SOLO",
                sku="24001",
                description=None,
                station="barra",
                status="inactive",
                catalog_scope="organization",
                source_branch_id=None,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(RecipeCatalogSeedError, match="pending catalog product already exists"):
            build_seed_plan(session)
    finally:
        session.close()


def test_dry_run_rejects_a_preexisting_pending_inventory_item() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=False)
        now = _now()
        session.execute(
            models.inventory_items.insert().values(
                id="pending-item",
                organization_id=ORGANIZATION_ID,
                name="CAFE MOLIDO",
                sku="001026",
                base_unit_id="unit-KG",
                item_type="ingredient",
                category_name="ABARROTE",
                catalog_scope="organization",
                source_branch_id=None,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(
            RecipeCatalogSeedError, match="pending catalog inventory item already exists"
        ):
            build_seed_plan(session)
    finally:
        session.close()


def test_caller_transaction_rolls_back_the_entire_publication() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        plan = build_seed_plan(session)
        session.commit()
        tables = (
            models.product_categories,
            models.products,
            models.price_versions,
            models.inventory_items,
            models.recipes,
            models.recipe_components,
        )
        before = {
            table.name: session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
            for table in tables
        }
        session.commit()
        with pytest.raises(RuntimeError, match="forced rollback"):
            with session.begin():
                apply_seed_plan(session, plan)
                raise RuntimeError("forced rollback")
        after = {
            table.name: session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
            for table in tables
        }
        assert after == before
    finally:
        session.close()


def test_existing_06002_versions_and_commands_are_preserved_on_replay() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        dry_run = build_seed_plan(session).report(applied=False)
        assert dry_run["preserved_skus"] == [PRESERVED_SKU]
        assert dry_run["recipes_to_seed"] == 306
        assert dry_run["publishable_components"] == 1395
        assert dry_run["components_to_seed"] == 1386
        first = apply_seed_plan(session, build_seed_plan(session))
        second = apply_seed_plan(session, build_seed_plan(session))
        versions = session.execute(
            sa.select(models.recipes.c.id, models.recipes.c.status)
            .where(models.recipes.c.product_id == "prod-06002")
            .order_by(models.recipes.c.version)
        ).all()
        commands = session.execute(
            sa.select(sa.func.count())
            .select_from(models.recipe_version_commands)
            .where(models.recipe_version_commands.c.product_id == "prod-06002")
        ).scalar_one()
        assert [row.id for row in versions] == [
            "recipe-06002-v1",
            "recipe-06002-v2",
            "recipe-06002-v3",
            "recipe-06002-v4",
        ]
        assert versions[-1].status == "active"
        assert commands == 4
        component_count = session.execute(
            sa.select(sa.func.count())
            .select_from(models.recipe_components)
            .where(models.recipe_components.c.recipe_id == "recipe-06002-v4")
        ).scalar_one()
        assert component_count == 11
        assert first["preserved_skus"] == [PRESERVED_SKU]
        assert second["preserved_skus"] == [PRESERVED_SKU]
        assert first["recipes_to_seed"] == 306
        assert second["recipes_to_seed"] == 0
        assert second["recipes_replayed"] == 306
        assert second["components_to_seed"] == 0
        unit_mismatches = session.execute(
            sa.select(sa.func.count())
            .select_from(
                models.recipe_components.join(
                    models.inventory_items,
                    models.recipe_components.c.item_id == models.inventory_items.c.id,
                )
            )
            .where(models.recipe_components.c.unit_id != models.inventory_items.c.base_unit_id)
        ).scalar_one()
        assert unit_mismatches == 0
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.products).where(
                models.products.c.sku.in_(PENDING_RECIPE_SKUS)
            )
        ).scalar_one() == 0
    finally:
        session.close()


def test_manifest_hash_rejects_tampering_with_unchanged_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tampered = tmp_path / "recipes.json"
    content = MANIFEST_PATH.read_text(encoding="utf-8")
    tampered.write_text(content.replace("ENSALADA", "ENSALADX", 1), encoding="utf-8")
    monkeypatch.setattr(recipe_catalog_seed, "MANIFEST_PATH", tampered)
    with pytest.raises(RecipeCatalogSeedError, match="manifest hash differs"):
        recipe_catalog_seed._load_manifest()


def test_dry_run_rejects_drift_in_a_deterministic_replay() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        apply_seed_plan(session, build_seed_plan(session))
        deterministic_recipe_id = recipe_catalog_seed._id("recipe", ORGANIZATION_ID, "01001")
        session.execute(
            models.recipe_components.update()
            .where(models.recipe_components.c.recipe_id == deterministic_recipe_id)
            .values(net_quantity=Decimal("999"))
        )
        with pytest.raises(RecipeCatalogSeedError, match="component differs"):
            build_seed_plan(session)
    finally:
        session.close()


def test_replay_rejects_a_pending_product_added_after_publication() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        apply_seed_plan(session, build_seed_plan(session))
        beverages_id = session.execute(
            sa.select(models.product_categories.c.id).where(
                models.product_categories.c.name == "BEBIDAS"
            )
        ).scalar_one()
        session.execute(
            models.products.insert().values(
                id="pending-product-after-publication",
                organization_id=ORGANIZATION_ID,
                category_id=beverages_id,
                name="CAFE SOLO",
                sku="24001",
                description=None,
                station="barra",
                status="active",
                catalog_scope="organization",
                source_branch_id=None,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        with pytest.raises(RecipeCatalogSeedError, match="pending catalog product already exists"):
            build_seed_plan(session)
    finally:
        session.close()


def test_exact_canonical_units_are_preferred_when_aliases_also_exist() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=False)
        now = _now()
        for code, dimension, precision in (
            ("KILO", "mass", 6),
            ("LITRO", "volume", 6),
            ("PZA", "discrete", 0),
        ):
            session.execute(
                models.inventory_units.insert().values(
                    id=f"canonical-{code}",
                    organization_id=ORGANIZATION_ID,
                    code=code,
                    name=code,
                    dimension=dimension,
                    precision_scale=precision,
                    created_at=now,
                )
            )
        plan = build_seed_plan(session)
        assert plan.unit_ids == {
            "KILO": "canonical-KILO",
            "LITRO": "canonical-LITRO",
            "PZA": "canonical-PZA",
        }
        apply_seed_plan(session, plan)
        unit_mismatches = session.execute(
            sa.select(sa.func.count())
            .select_from(
                models.recipe_components.join(
                    models.inventory_items,
                    models.recipe_components.c.item_id == models.inventory_items.c.id,
                )
            )
            .where(models.recipe_components.c.unit_id != models.inventory_items.c.base_unit_id)
        ).scalar_one()
        assert unit_mismatches == 0
    finally:
        session.close()


def test_guarded_publication_requires_environment_actor_and_exact_plan() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        with pytest.raises(RecipeCatalogSeedError, match="environment confirmation differs"):
            publish_recipe_catalog(
                session,
                apply=False,
                actor_user_id="actor-history",
                configured_environment="production",
                confirmed_environment="test",
            )
        dry_run = publish_recipe_catalog(
            session,
            apply=False,
            actor_user_id="actor-history",
            configured_environment="production",
            confirmed_environment="production",
        )
        assert dry_run["dry_run"] is True
        assert dry_run["recipes_to_seed"] == 306
        assert dry_run["categories_to_create"] == []
        assert dry_run["manifest_sha256"] == MANIFEST_SHA256

        result = publish_recipe_catalog(
            session,
            apply=True,
            actor_user_id="actor-history",
            configured_environment="production",
            confirmed_environment="production",
        )
        replay = publish_recipe_catalog(
            session,
            apply=True,
            actor_user_id="actor-history",
            configured_environment="production",
            confirmed_environment="production",
        )
        audits = session.execute(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "recipe_catalog.applied")
        ).scalar_one()
        assert result["applied"] is True
        assert result["replayed"] is False
        assert replay["applied"] is False
        assert replay["replayed"] is True
        assert audits == 1
        audit_payload = session.execute(
            sa.select(models.audit_events.c.payload).where(
                models.audit_events.c.action == "recipe_catalog.applied"
            )
        ).scalar_one()
        assert audit_payload["categories_created"] == []
        assert audit_payload["publishable_components"] == 1395
        assert audit_payload["seeded_components"] == 1386
        assert audit_payload["pending_recipe_skus"] == sorted(PENDING_RECIPE_SKUS)
        assert audit_payload["pending_item_skus"] == sorted(PENDING_ITEM_SKUS)
    finally:
        session.close()


def test_guarded_publication_rejects_active_actor_without_organization_authority() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        session.execute(
            models.role_authority_grants.delete().where(
                models.role_authority_grants.c.role_id == "role-recipe-publisher"
            )
        )
        with pytest.raises(RecipeCatalogSeedError, match="organization recipes authority"):
            publish_recipe_catalog(
                session,
                apply=False,
                actor_user_id="actor-history",
                configured_environment="production",
                confirmed_environment="production",
            )
    finally:
        session.close()


def test_publication_does_not_use_a_preexisting_pending_category() -> None:
    session = _session()
    try:
        _seed_scope(session, with_history=True)
        now = _now()
        session.execute(
            models.product_categories.insert().values(
                id=recipe_catalog_seed._id("product-category", ORGANIZATION_ID, "CAFE Y MACCHA"),
                organization_id=ORGANIZATION_ID,
                name="CAFE Y MACCHA",
                display_order=2,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        before_products = session.execute(
            sa.select(sa.func.count()).select_from(models.products)
        ).scalar_one()
        result = publish_recipe_catalog(
            session,
            apply=True,
            actor_user_id="actor-history",
            configured_environment="production",
            confirmed_environment="production",
        )
        assert result["categories_to_create"] == []
        assert (
            session.execute(sa.select(sa.func.count()).select_from(models.products)).scalar_one()
            == before_products
        )
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "recipe_catalog.applied")
            ).scalar_one()
            == 1
        )
    finally:
        session.close()


def test_operational_entrypoint_requires_reviewed_hash_and_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        recipe_catalog_seed,
        "get_settings",
        lambda: SimpleNamespace(database_url="configured", environment="production"),
    )
    with pytest.raises(SystemExit, match="manifest_confirmation_required"):
        main(
            [
                "--actor",
                "actor-history",
                "--confirm-environment",
                "production",
                "--confirm-manifest-sha256",
                "wrong",
            ]
        )
    with pytest.raises(SystemExit, match="plan_confirmation_required"):
        main(
            [
                "--actor",
                "actor-history",
                "--confirm-environment",
                "production",
                "--confirm-manifest-sha256",
                MANIFEST_SHA256,
                "--confirm-plan",
                "wrong",
                "--apply",
            ]
        )


def test_operational_entrypoint_requires_the_reviewed_schema_head() -> None:
    session = _session()
    try:
        session.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(64))"))
        session.execute(
            sa.text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
            {"head": PRODUCTION_SCHEMA_HEAD},
        )
        _require_reviewed_schema_head(session)
        session.execute(sa.text("UPDATE alembic_version SET version_num = 'unexpected_revision'"))
        with pytest.raises(RecipeCatalogSeedError, match="requires schema head"):
            _require_reviewed_schema_head(session)
    finally:
        session.close()

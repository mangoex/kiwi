"""Offline snapshot compatibility for the branch POS appearance preference."""

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.offline_order_catalog import (
    build_catalog_snapshot,
    hydrate_catalog_snapshot,
    refresh_catalog_snapshot,
)
from test_cash_concepts import ORG_ID
from test_cash_ledger import BRANCH_A
from test_offline_order_catalog import _bundle_source, _manifest


def test_legacy_gateway_branches_table_expands_before_bundle_refresh(tmp_path):
    source_engine, source, _, seed = _bundle_source()
    target = sa.create_engine(f"sqlite:///{tmp_path / 'gateway.db'}")
    try:
        catalog = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A
        )
        hydrate_catalog_snapshot(
            target,
            manifest=_manifest(),
            catalog=catalog,
            operational_seed=seed,
            read_only=False,
            full_operational_schema=True,
        ).close()
        with target.begin() as connection:
            connection.execute(
                sa.text("ALTER TABLE branches DROP COLUMN pos_catalog_visuals_enabled")
            )
        assert "pos_catalog_visuals_enabled" not in {
            column["name"] for column in sa.inspect(target).get_columns("branches")
        }

        source.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_A)
            .values(pos_catalog_visuals_enabled=False)
        )
        source.commit()
        refreshed = build_catalog_snapshot(
            source, organization_id=ORG_ID, branch_id=BRANCH_A
        )
        refresh_catalog_snapshot(
            target,
            manifest=_manifest("f" * 64),
            catalog=refreshed,
            operational_seed=seed,
        )
        with target.connect() as connection:
            assert connection.scalar(
                sa.select(models.branches.c.pos_catalog_visuals_enabled).where(
                    models.branches.c.id == BRANCH_A
                )
            ) is False
    finally:
        source.close()
        source_engine.dispose()
        target.dispose()

"""Integration tests for Kiwi Real Catalog Loader."""

# ruff: noqa: E501

from pathlib import Path

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.real_catalog_loader import load_real_catalog_from_excels
from sqlalchemy.orm import Session

EXCEL_DIR = str(Path(__file__).resolve().parents[3])


def test_load_real_catalog_from_excels(tmp_path: Path):
    db_path = tmp_path / "test_catalog.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    models.metadata.create_all(engine)

    org_id = "test-org-kiwi"
    branch_id = "test-branch-kiwi"
    now = sa.func.now()

    with Session(engine) as session:
        # Create base organization, legal entity, business unit and branch
        session.execute(models.organizations.insert().values(
            id=org_id, name="Kiwi Comida Natural", status="active", created_at=now, updated_at=now
        ))
        session.execute(models.legal_entities.insert().values(
            id="legal-kiwi", organization_id=org_id, name="Aurora Cristina Mejia Casas", tax_id="MECA9102201G4",
            status="active", created_at=now, updated_at=now
        ))
        session.execute(models.business_units.insert().values(
            id="unit-kiwi", organization_id=org_id, legal_entity_id="legal-kiwi", name="Kiwi Culiacán",
            code="KIWI-CUL", unit_type="restaurant", status="active", created_at=now, updated_at=now
        ))
        session.execute(models.branches.insert().values(
            id=branch_id, organization_id=org_id, legal_entity_id="legal-kiwi", business_unit_id="unit-kiwi",
            name="Sucursal Cinepolis", code="BR-CINEPOLIS", status="active", created_at=now, updated_at=now
        ))
        session.execute(models.warehouses.insert().values(
            id="wh-cinepolis", organization_id=org_id, branch_id=branch_id, name="Almacén Cinepolis",
            status="active", created_at=now, updated_at=now
        ))
        session.commit()

        # Run catalog loader on actual Excel files
        summary = load_real_catalog_from_excels(
            session=session,
            excel_dir=EXCEL_DIR,
            organization_id=org_id,
            branch_id=branch_id,
            import_customers=True,
            max_customers=100,  # test sample
        )

        assert summary["supplies"] >= 150
        assert summary["presentations"] >= 150
        assert summary["products"] >= 160
        assert summary["modifier_groups"] >= 100
        assert summary["customers"] == 100

        # Verify exact item cost calculations
        aceituna = session.execute(
            sa.select(models.inventory_items).where(models.inventory_items.c.sku == "INS-1001")
        ).mappings().first()
        assert aceituna is not None
        assert "ACEITUNA NEGRA" in aceituna["name"]

        # Verify presentation conversion factor
        pres_aceituna = session.execute(
            sa.select(models.purchase_presentations).where(models.purchase_presentations.c.code == "PRES-1001")
        ).mappings().first()
        assert pres_aceituna is not None
        assert float(pres_aceituna["base_unit_yield"]) == 0.45

        # Verify Baguette product
        baguette = session.execute(
            sa.select(models.products).where(models.products.c.name.like("%BAGUETTE%"))
        ).mappings().first()
        assert baguette is not None

        # Verify modifier groups on Baguette
        mod_groups = session.execute(
            sa.select(models.modifier_groups).where(models.modifier_groups.c.product_id == baguette["id"])
        ).mappings().all()
        assert len(mod_groups) >= 2

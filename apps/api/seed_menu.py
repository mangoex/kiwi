# ruff: noqa: E501
import os
import sys
import uuid
from datetime import datetime, timezone
UTC = timezone.utc

UTC = UTC

import sqlalchemy as sa
from sqlalchemy.orm import Session

# Add the apps/api path so we can import restaurant_os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from restaurant_os import models
from restaurant_os.database import get_engine


def _now():
    return datetime.now(UTC)

def get_or_create_org(session: Session) -> str:
    org_id = session.scalar(sa.select(models.organizations.c.id).limit(1))
    if not org_id:
        org_id = str(uuid.uuid4())
        session.execute(
            models.organizations.insert().values(
                id=org_id,
                name="Kiwi Restaurante",
                status="active",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        print("Created default organization.")
    return org_id

def get_or_create_branch(session: Session, org_id: str) -> str:
    branch_id = session.scalar(
        sa.select(models.branches.c.id).where(models.branches.c.organization_id == org_id).limit(1)
    )
    if not branch_id:
        # Create legal entity first
        legal_entity_id = str(uuid.uuid4())
        session.execute(
            models.legal_entities.insert().values(
                id=legal_entity_id,
                organization_id=org_id,
                name="Kiwi S.A. de C.V.",
                status="active",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        branch_id = str(uuid.uuid4())
        session.execute(
            models.branches.insert().values(
                id=branch_id,
                organization_id=org_id,
                legal_entity_id=legal_entity_id,
                name="Kiwi Matriz",
                code="MTZ",
                status="active",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        print("Created default branch.")
    return branch_id


def seed():
    with Session(get_engine()) as session:
        org_id = get_or_create_org(session)
        branch_id = get_or_create_branch(session, org_id)

        # 1. CATEGORIAS
        cats = [
            ("Jugos y Extractos", 1),
            ("Café y Matcha", 2),
            ("Smoothies y Licuados", 3),
            ("Aguas y Bebidas", 4),
            ("Panadería", 5),
            ("Ensaladas", 6),
            ("Emparedados y Sandos", 7),
            ("Frutas", 8),
            ("Combos", 9)
        ]
        
        category_ids = {}
        for name, order in cats:
            existing = session.scalar(
                sa.select(models.product_categories.c.id)
                .where(models.product_categories.c.organization_id == org_id)
                .where(models.product_categories.c.name == name)
            )
            if existing:
                category_ids[name] = existing
            else:
                cid = str(uuid.uuid4())
                session.execute(
                    models.product_categories.insert().values(
                        id=cid,
                        organization_id=org_id,
                        name=name,
                        display_order=order,
                        status="active",
                        created_at=_now(),
                        updated_at=_now()
                    )
                )
                category_ids[name] = cid

        # 2. UNIDADES
        units = [
            ("KG", "Kilogramo", 3),
            ("L", "Litro", 3),
            ("PZ", "Pieza", 0),
            ("POR", "Porción", 0)
        ]
        unit_ids = {}
        for code, name, prec in units:
            existing = session.scalar(
                sa.select(models.inventory_units.c.id)
                .where(models.inventory_units.c.organization_id == org_id)
                .where(models.inventory_units.c.code == code)
            )
            if existing:
                unit_ids[code] = existing
            else:
                uid = str(uuid.uuid4())
                session.execute(
                    models.inventory_units.insert().values(
                        id=uid,
                        organization_id=org_id,
                        code=code,
                        name=name,
                        precision_scale=prec,
                        created_at=_now()
                    )
                )
                unit_ids[code] = uid

        # 3. INSUMOS
        insumos = [
            # Frutas y Verduras (KG)
            ("Naranja", "INS-NAR", "KG"),
            ("Piña", "INS-PIN", "KG"),
            ("Pepino", "INS-PEP", "KG"),
            ("Apio", "INS-API", "KG"),
            ("Nopal", "INS-NOP", "KG"),
            ("Papaya", "INS-PAP", "KG"),
            ("Fresa", "INS-FRE", "KG"),
            ("Manzana", "INS-MAN", "KG"),
            ("Limón", "INS-LIM", "KG"),
            ("Zanahoria", "INS-ZAN", "KG"),
            ("Betabel", "INS-BET", "KG"),
            ("Espinaca", "INS-ESP", "KG"),
            ("Plátano", "INS-PLA", "KG"),
            ("Melón", "INS-MEL", "KG"),
            ("Jengibre", "INS-JEN", "KG"),
            ("Jícama", "INS-JIC", "KG"),
            ("Aguacate", "INS-AGU", "KG"),
            ("Tomates Cherry", "INS-TOMC", "KG"),
            ("Gajos de tomate", "INS-TOMG", "KG"),
            ("Cebolla", "INS-CEB", "KG"),
            # Lácteos y Líquidos (L)
            ("Leche Entera", "INS-LEC-ENT", "L"),
            ("Leche Deslactosada", "INS-LEC-DES", "L"),
            ("Leche Almendra", "INS-LEC-ALM", "L"),
            ("Leche Coco", "INS-LEC-COC", "L"),
            ("Yogurt Natural", "INS-YOG", "L"),
            ("Lecherita", "INS-LECHERITA", "L"),
            # Granos y Semillas (KG)
            ("Avena", "INS-AVE", "KG"),
            ("Chía", "INS-CHI", "KG"),
            ("Nuez", "INS-NUE", "KG"),
            ("Ajonjolí", "INS-AJO", "KG"),
            ("Cacahuates garapiñados", "INS-CAC", "KG"),
            ("Semillas de girasol", "INS-GIR", "KG"),
            ("Quinoa", "INS-QUI", "KG"),
            ("Amaranto", "INS-AMA", "KG"),
            ("Pasas", "INS-PAS", "KG"),
            # Abarrotes y Varios (KG / PZ)
            ("Miel de abeja", "INS-MIE", "KG"),
            ("Dátil", "INS-DAT", "KG"),
            ("Cacao", "INS-CAC-POL", "KG"),
            ("Proteína en polvo", "INS-PROT", "KG"),
            ("Café en grano", "INS-CAF", "KG"),
            ("Matcha", "INS-MAT", "KG"),
            # Proteínas y Quesos (KG)
            ("Pollo a la plancha", "INS-POL-PLA", "KG"),
            ("Pollo BBQ", "INS-POL-BBQ", "KG"),
            ("Jamón", "INS-JAM", "KG"),
            ("Atún", "INS-ATU", "KG"),
            ("Queso Cabra", "INS-QUE-CAB", "KG"),
            ("Queso Panela", "INS-QUE-PAN", "KG"),
            ("Philadelphia", "INS-PHI", "KG"),
            ("Mezcla Quesos", "INS-QUE-MIX", "KG"),
            # Panadería (PZ)
            ("Pan Cuernito", "INS-PAN-CUE", "PZ"),
            ("Pan Baguette", "INS-PAN-BAG", "PZ"),
            ("Pan Focaccia", "INS-PAN-FOC", "PZ"),
            ("Pan Sándwich", "INS-PAN-SAN", "PZ"),
            ("Tostaditas horneadas", "INS-TOS-HOR", "KG"),
            ("Tostaditas crujientes", "INS-TOS-CRU", "KG"),
            # Otros
            ("Pasta Fusili", "INS-FUS", "KG"),
            ("Aceitunas negras", "INS-ACE", "KG"),
            ("Granos de elote", "INS-ELO", "KG"),
            ("Aderezo balsámico", "INS-ADE-BAL", "L"),
            ("Aderezo cilantro", "INS-ADE-CIL", "L"),
            ("Aderezo casa", "INS-ADE-CAS", "L"),
            ("Germinado de alfalfa", "INS-GER", "KG"),
            ("Galleta chispas", "INS-GAL-CHI", "PZ")
        ]

        item_ids = {}
        for name, sku, unit_code in insumos:
            existing = session.scalar(
                sa.select(models.inventory_items.c.id)
                .where(models.inventory_items.c.organization_id == org_id)
                .where(models.inventory_items.c.sku == sku)
            )
            if existing:
                item_ids[sku] = existing
            else:
                iid = str(uuid.uuid4())
                session.execute(
                    models.inventory_items.insert().values(
                        id=iid,
                        organization_id=org_id,
                        name=name,
                        sku=sku,
                        base_unit_id=unit_ids[unit_code],
                        item_type="ingredient",
                        status="active",
                        created_at=_now(),
                        updated_at=_now()
                    )
                )
                item_ids[sku] = iid

        # 4. PRODUCTOS, PRECIOS, RECETAS
        # (name, sku, category, price, description, components_sku_list)
        menu = [
            # Jugos
            ("Jugo Verde", "JUG-VER", "Jugos y Extractos", 65, "Naranja, piña, pepino, apio y nopal.", ["INS-NAR", "INS-PIN", "INS-PEP", "INS-API", "INS-NOP"]),
            ("Jugo Relajante", "JUG-REL", "Jugos y Extractos", 65, "Naranja, papaya y avena.", ["INS-NAR", "INS-PAP", "INS-AVE"]),
            ("Jugo Vitamínico", "JUG-VIT", "Jugos y Extractos", 65, "Naranja, fresa, manzana y pepino.", ["INS-NAR", "INS-FRE", "INS-MAN", "INS-PEP"]),
            ("Jugo Energetizante", "JUG-ENE", "Jugos y Extractos", 65, "Naranja, piña y limón.", ["INS-NAR", "INS-PIN", "INS-LIM"]),
            ("Jugo Anti-anemia", "JUG-ANT", "Jugos y Extractos", 65, "Naranja, zanahoria y betabel.", ["INS-NAR", "INS-ZAN", "INS-BET"]),
            
            # Extractos y Shots
            ("Extracto Verde", "EXT-VER", "Jugos y Extractos", 63, "Mezcla de pepino, apio, espinaca verde, jugo de limón y acidita manzana verde.", ["INS-PEP", "INS-API", "INS-ESP", "INS-LIM", "INS-MAN"]),
            ("Extracto Rojo", "EXT-ROJ", "Jugos y Extractos", 63, "Fresco sabor del pepino con apio, betabel, jugo de limón y dulce de la manzana roja.", ["INS-PEP", "INS-API", "INS-BET", "INS-LIM", "INS-MAN"]),
            ("Shot Jengibre-Piña", "SHO-JEN", "Jugos y Extractos", 40, "Energizante mezcla de extracto de jengibre y rico jugo de piña.", ["INS-JEN", "INS-PIN"]),

            # Café y Matcha
            ("Kiwi Latte", "CAF-LAT", "Café y Matcha", 70, "", ["INS-CAF", "INS-LEC-ENT"]),
            ("Kiwi Latte Fresh", "CAF-LAT-FRE", "Café y Matcha", 80, "", ["INS-CAF", "INS-LEC-ENT"]),
            ("Café Solo", "CAF-SOL", "Café y Matcha", 50, "", ["INS-CAF"]),
            ("Café Solo Fresh", "CAF-SOL-FRE", "Café y Matcha", 55, "", ["INS-CAF"]),
            ("Café Naranja", "CAF-NAR", "Café y Matcha", 75, "", ["INS-CAF", "INS-NAR"]),
            ("Maccha Shiru", "MAT-SHI", "Café y Matcha", 120, "", ["INS-MAT"]),
            ("Maccha Pinku (con fresa)", "MAT-PIN", "Café y Matcha", 130, "", ["INS-MAT", "INS-FRE"]),

            # Smoothies
            ("Smoothie Fresh", "SMO-FRE", "Smoothies y Licuados", 90, "Manzana, leche de almendra, miel de abeja, dátil, chía y espinaca.", ["INS-MAN", "INS-LEC-ALM", "INS-MIE", "INS-DAT", "INS-CHI", "INS-ESP"]),
            ("Smoothie Rosa", "SMO-ROS", "Smoothies y Licuados", 90, "Fresa con leche de almendra, miel de abeja, dátil, chía y espinaca.", ["INS-FRE", "INS-LEC-ALM", "INS-MIE", "INS-DAT", "INS-CHI", "INS-ESP"]),
            ("Smoothie Cacao", "SMO-CAC", "Smoothies y Licuados", 90, "Plátano, leche de almendra, miel de abeja, cacao, chía y espinaca.", ["INS-PLA", "INS-LEC-ALM", "INS-MIE", "INS-CAC-POL", "INS-CHI", "INS-ESP"]),
            ("Smoothie Pro", "SMO-PRO", "Smoothies y Licuados", 120, "Smoothie Fresh, Rosa o Cacao con scoop de proteína.", ["INS-PROT", "INS-LEC-ALM"]),

            # Panadería
            ("Bisquet", "PAN-BIS", "Panadería", 35, "", []),
            ("Baguette", "PAN-BAG", "Panadería", 26, "", ["INS-PAN-BAG"]),
            ("Cuernito Jamón/Phila", "PAN-CUE", "Panadería", 38, "Relleno de jamón y philadelphia.", ["INS-PAN-CUE", "INS-JAM", "INS-PHI"]),
            ("Barra de pan sándwich", "PAN-BAR", "Panadería", 60, "", ["INS-PAN-SAN"]),
            
            # Ensaladas
            ("Ensalada Manzana Nuez", "ENS-MAN", "Ensaladas", 120, "Lechuga, queso de cabra, nuez, dulces cubitos de manzana, ajonjolí y aderezo balsámico.", ["INS-LEC-ENT", "INS-QUE-CAB", "INS-NUE", "INS-MAN", "INS-AJO", "INS-ADE-BAL"]),
            ("Ensalada Frutos Rojos", "ENS-FRU", "Ensaladas", 125, "Lechuga, fresa, arándanos, queso panela, cacahuates garapiñados y aderezo balsámico.", ["INS-LEC-ENT", "INS-FRE", "INS-QUE-PAN", "INS-CAC", "INS-ADE-BAL"]),
            ("Ensalada Del Chef", "ENS-CHE", "Ensaladas", 125, "Lechuga, pollo a la plancha, pepino, jamón, panela, tostaditas, germinado, gajos de tomate, cebolla, aderezo.", ["INS-LEC-ENT", "INS-POL-PLA", "INS-PEP", "INS-JAM", "INS-QUE-PAN", "INS-TOS-HOR", "INS-GER", "INS-TOMG", "INS-CEB", "INS-ADE-CAS"]),
            
            # Emparedados (Simplified to unique items)
            ("Emparedado de Pollo", "EMP-POL", "Emparedados y Sandos", 115, "Con Cuernito, Baguette o Focaccia.", ["INS-PAN-CUE", "INS-POL-PLA"]),
            ("Sando Kyoto Pollo BBQ", "SAN-KYO-BBQ", "Emparedados y Sandos", 120, "Sandwich tipo Sando relleno.", ["INS-PAN-SAN", "INS-POL-BBQ"]),
            
            # Combos
            ("Combo Ligero", "COM-LIG", "Combos", 105, "Sándwich básico + fresco jugo de naranja del día + dulce galleta con chispas.", ["INS-PAN-SAN", "INS-JAM", "INS-QUE-PAN", "INS-NAR", "INS-GAL-CHI"]),
            ("Combo Premium", "COM-PRE", "Combos", 180, "Media ensalada premium y medio baguette de pollo, pollo bbq o atún.", ["INS-LEC-ENT", "INS-PAN-BAG", "INS-POL-PLA"])
        ]

        print("Seeding products...")
        for name, sku, cat, price, desc, comp_skus in menu:
            # Check if product exists
            existing_prod = session.scalar(
                sa.select(models.products.c.id)
                .where(models.products.c.organization_id == org_id)
                .where(models.products.c.sku == sku)
            )
            
            if existing_prod:
                prod_id = existing_prod
            else:
                prod_id = str(uuid.uuid4())
                session.execute(
                    models.products.insert().values(
                        id=prod_id,
                        organization_id=org_id,
                        category_id=category_ids[cat],
                        name=name,
                        sku=sku,
                        description=desc,
                        station="cocina" if "Ensalada" in name or "Sando" in name else "barra",
                        status="active",
                        created_at=_now(),
                        updated_at=_now()
                    )
                )
                
                # Assign to branch
                session.execute(
                    models.branch_product_availability.insert().values(
                        branch_id=branch_id,
                        product_id=prod_id,
                        is_available=True,
                        updated_at=_now()
                    )
                )
                
                # Set price
                price_id = str(uuid.uuid4())
                session.execute(
                    models.price_versions.insert().values(
                        id=price_id,
                        organization_id=org_id,
                        product_id=prod_id,
                        price_cents=price * 100,
                        currency="MXN",
                        valid_from=_now(),
                        created_at=_now()
                    )
                )

            # Check if recipe exists
            existing_recipe = session.scalar(
                sa.select(models.recipes.c.id)
                .where(models.recipes.c.organization_id == org_id)
                .where(models.recipes.c.product_id == prod_id)
                .where(models.recipes.c.version == 1)
            )

            if not existing_recipe:
                rec_id = str(uuid.uuid4())
                session.execute(
                    models.recipes.insert().values(
                        id=rec_id,
                        organization_id=org_id,
                        product_id=prod_id,
                        version=1,
                        status="active",
                        yield_quantity=1,
                        yield_unit_id=unit_ids["POR"],
                        created_at=_now()
                    )
                )
                
                for c_sku in comp_skus:
                    if c_sku in item_ids:
                        session.execute(
                            models.recipe_components.insert().values(
                                recipe_id=rec_id,
                                item_id=item_ids[c_sku],
                                quantity_base_units=100 # Default to 100g or 100ml for simplicity of mocking
                            )
                        )

        session.commit()
        print("Done seeding.")

if __name__ == "__main__":
    seed()

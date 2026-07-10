import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlalchemy as sa
from restaurant_os.database import get_engine
from restaurant_os.models import (
    branches,
    cash_shifts,
    legal_entities,
    order_lines,
    orders,
    organizations,
    payments,
    products,
    warehouses,
)


def generate_uuid():
    return str(uuid.uuid4())


def seed():
    engine = get_engine()
    with engine.begin() as conn:
        # Get the first organization or create one
        orgs = conn.execute(sa.select(organizations)).fetchall()
        if not orgs:
            org_id = generate_uuid()
            conn.execute(
                organizations.insert().values(
                    id=org_id,
                    name="Default Org",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            org_id = orgs[0].id

        # Get or create legal entity
        les = conn.execute(
            sa.select(legal_entities).where(legal_entities.c.organization_id == org_id)
        ).fetchall()
        if not les:
            le_id = generate_uuid()
            conn.execute(
                legal_entities.insert().values(
                    id=le_id,
                    organization_id=org_id,
                    name="Default Legal Entity",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            le_id = les[0].id

        # Seed 7 branches
        branch_names = [
            "Centro Histórico",
            "Plaza Mayor",
            "Zona Norte",
            "Aeropuerto",
            "Distrito Financiero",
            "Campus Sur",
            "Paseo de la Reforma"
        ]

        branch_ids = []
        for i, name in enumerate(branch_names):
            # check if exists
            code = f"BR-{i+1:03d}"
            existing = conn.execute(sa.select(branches).where(branches.c.code == code)).first()
            if not existing:
                b_id = generate_uuid()
                conn.execute(
                    branches.insert().values(
                        id=b_id,
                        organization_id=org_id,
                        legal_entity_id=le_id,
                        name=name,
                        code=code,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
                
                # Each branch needs a warehouse
                conn.execute(
                    warehouses.insert().values(
                        id=generate_uuid(),
                        organization_id=org_id,
                        branch_id=b_id,
                        name=f"Almacén {name}",
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
                branch_ids.append(b_id)
            else:
                branch_ids.append(existing.id)
                
        # Get some products to create orders
        prods = conn.execute(sa.select(products)).fetchall()
        if not prods:
            print("No products found. Make sure to run seed_menu.py first.")
            return

        # Generate cash shifts and orders for the last 30 days
        print("Generating mock sales data...")
        now = datetime.now(UTC)
        
        for branch_id in branch_ids:
            # 1 to 2 registers per branch
            num_registers = random.choice([1, 2])
            for r in range(num_registers):
                register_code = f"CAJA-{r+1:02d}"
                
                # Create a few cash shifts over the last 30 days
                for days_ago in range(30, -1, -5): # every 5 days create a shift
                    shift_date = now - timedelta(days=days_ago)
                    shift_id = generate_uuid()
                    
                    conn.execute(
                        cash_shifts.insert().values(
                            id=shift_id,
                            organization_id=org_id,
                            branch_id=branch_id,
                            register_code=register_code,
                            status="CLOSED" if days_ago > 0 else "OPEN",
                            opening_cash_cents=100000, # $1000 MXN
                            opened_at=shift_date - timedelta(hours=8),
                            closed_at=shift_date if days_ago > 0 else None,
                            created_at=shift_date - timedelta(hours=8),
                        )
                    )
                    
                    # Generate 5-15 orders per shift
                    num_orders = random.randint(5, 15)
                    for _o in range(num_orders):
                        order_id = generate_uuid()
                        order_total = 0
                        order_date = shift_date - timedelta(
                            hours=random.randint(0, 7), 
                            minutes=random.randint(0, 59)
                        )
                        
                        # Generate lines
                        num_lines = random.randint(1, 4)
                        for _ in range(num_lines):
                            p = random.choice(prods)
                            qty = random.randint(1, 3)
                            # Mock price if missing
                            price_cents = 15000 # $150
                            
                            line_total = price_cents * qty
                            order_total += line_total
                            
                            conn.execute(
                                order_lines.insert().values(
                                    id=generate_uuid(),
                                    order_id=order_id,
                                    product_id=p.id,
                                    product_name=p.name,
                                    quantity=qty,
                                    unit_price_cents=price_cents,
                                    line_total_cents=line_total,
                                    station=p.station,
                                    created_at=order_date,
                                )
                            )
                            
                        # Insert Order
                        conn.execute(
                            orders.insert().values(
                                id=order_id,
                                organization_id=org_id,
                                branch_id=branch_id,
                                cash_shift_id=shift_id,
                                folio=f"ORD-{order_date.strftime('%Y%m%d%H%M%S')}-{random.randint(100,999)}",
                                channel="pos",
                                status="completed",
                                total_cents=order_total,
                                order_type=random.choice(["dine-in", "takeout", "delivery"]),
                                created_at=order_date,
                                accepted_at=order_date + timedelta(minutes=1),
                            )
                        )
                        
                        # Insert Payment
                        conn.execute(
                            payments.insert().values(
                                id=generate_uuid(),
                                organization_id=org_id,
                                branch_id=branch_id,
                                order_id=order_id,
                                cash_shift_id=shift_id,
                                method=random.choice(["cash", "card"]),
                                status="completed",
                                amount_cents=order_total,
                                confirmed_at=order_date + timedelta(minutes=2),
                                created_at=order_date + timedelta(minutes=2),
                            )
                        )

        print("Successfully seeded 7 branches, registers, and mock sales data.")

if __name__ == "__main__":
    seed()

import sys
sys.path.append('apps/api')
import os
os.environ["DATABASE_URL"] = "sqlite:///local.db"
os.environ["SECRET_KEY"] = "dummy"
from datetime import datetime, timezone
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from restaurant_os.models import metadata, orders, audit_events
from restaurant_os.platform_data import get_dashboard_overview

engine = create_engine("sqlite:///local.db")
metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

branch_id = str(uuid.uuid4())
org_id = str(uuid.uuid4())
cash_shift_id = str(uuid.uuid4())

try:
    session.execute(orders.insert().values(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        branch_id=branch_id,
        cash_shift_id=cash_shift_id,
        folio="FOLIO-123",
        channel="pos",
        status="CLOSED",
        total_cents=15000,
        currency="MXN",
        created_at=datetime.now(timezone.utc)
    ))
    
    session.execute(audit_events.insert().values(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        branch_id=branch_id,
        action="cash_shift.opened",
        entity_type="cash_shift",
        entity_id=cash_shift_id,
        payload={"opened_by": "Test User"},
        created_at=datetime.now(timezone.utc)
    ))
    
    session.commit()
    
    print("Testing get_dashboard_overview...")
    res = get_dashboard_overview(session, branch_id=branch_id)
    print("Recent transactions:")
    print(res["recent_transactions"])
    print("Recent notifications:")
    print(res["recent_notifications"])
except Exception as e:
    print("Error:", e)
finally:
    session.close()

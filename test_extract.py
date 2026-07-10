import sys
sys.path.append('apps/api')
import os
os.environ["DATABASE_URL"] = "sqlite:///local.db"
os.environ["SECRET_KEY"] = "dummy"
from sqlalchemy import create_engine, select, extract
from sqlalchemy.orm import sessionmaker
from restaurant_os.models import metadata, orders

engine = create_engine("sqlite:///local.db")
metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

try:
    q = select(orders).where(extract('year', orders.c.created_at) == 2024)
    session.execute(q).fetchall()
    print("EXTRACT WORKS!")
except Exception as e:
    print("EXTRACT FAILED:", e)

"""CORTE-CIEGO-001 phases 2-6: additive blind cash, alert and control evidence tables.

Additive only: no existing row, balance, payment or movement is rewritten. Downgrade is
blocked whenever any evidence row exists, so audit history can never be dropped silently.
"""

import sqlalchemy as sa
from alembic import op
from restaurant_os.blind_cash_phase2_schema import tables

revision = "0103_blind_cash_phases_2_6"
down_revision = "0102_order_exceptions"
branch_labels = depends_on = None


def relations() -> tuple[sa.Table, ...]:
    metadata = sa.MetaData()
    for name in ("organizations", "users", "branches", "user_cash_cuts"):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True))
    return tables(metadata)


def upgrade() -> None:
    bind = op.get_bind()
    for relation in relations():
        relation.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if any(bind.scalar(sa.select(sa.func.count()).select_from(table)) for table in relations()):
        raise RuntimeError("0103 downgrade blocked: blind cash or alert evidence exists")
    for relation in reversed(relations()):
        relation.drop(bind)

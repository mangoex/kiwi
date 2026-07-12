"""advanced recipes, costing, production batches and consumption snapshots

Revision ID: 0019_advanced_recipes_production
Revises: 0018_direct_purchases_cash_costing
Create Date: 2026-07-11 05:00:00
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0019_advanced_recipes_production"
down_revision: str | None = "0018_direct_purchases_cash_costing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRODUCTION_PERMISSION_ID = "018f6f73-2d0a-74f0-8f1c-000000000623"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
SUPERVISOR_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000016"


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO permissions (id, code, description, created_at)
        VALUES (:id, 'production.manage', 'Crear y confirmar lotes de produccion.', CURRENT_TIMESTAMP)
        ON CONFLICT (code) DO NOTHING
    """).bindparams(id=PRODUCTION_PERMISSION_ID))
    for role_id in (ADMIN_ROLE_ID, SUPERVISOR_ROLE_ID):
        op.execute(sa.text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT :role_id, id FROM permissions WHERE code = 'production.manage'
            ON CONFLICT DO NOTHING
        """).bindparams(role_id=role_id))
    with op.batch_alter_table("recipes") as batch:
        batch.alter_column("product_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("yield_quantity", existing_type=sa.Integer(), type_=sa.Numeric(18, 6), nullable=False)
        batch.add_column(sa.Column("output_item_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("branch_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("recipe_type", sa.String(24), nullable=False, server_default="sale"))
        batch.add_column(sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_recipes_output_item", "inventory_items", ["output_item_id"], ["id"])
        batch.create_foreign_key("fk_recipes_branch", "branches", ["branch_id"], ["id"])
        batch.create_unique_constraint("uq_recipes_output_item_version", ["output_item_id", "version"])
    op.execute(sa.text("UPDATE recipes SET valid_from = created_at, updated_at = created_at WHERE valid_from IS NULL"))
    with op.batch_alter_table("recipes") as batch:
        batch.alter_column("valid_from", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    with op.batch_alter_table("recipe_components") as batch:
        batch.alter_column("quantity_base_units", existing_type=sa.Integer(), type_=sa.Numeric(18, 6), nullable=False)
        batch.add_column(sa.Column("unit_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("net_quantity", sa.Numeric(18, 6), nullable=True))
        batch.add_column(sa.Column("waste_rate", sa.Numeric(9, 6), nullable=False, server_default="0"))
        batch.add_column(sa.Column("gross_quantity", sa.Numeric(18, 6), nullable=True))
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("notes", sa.String(400), nullable=True))
        batch.create_foreign_key("fk_recipe_components_unit", "inventory_units", ["unit_id"], ["id"])
    op.execute(sa.text("""
        UPDATE recipe_components
        SET unit_id = (SELECT base_unit_id FROM inventory_items WHERE inventory_items.id = recipe_components.item_id),
            net_quantity = quantity_base_units,
            gross_quantity = quantity_base_units
    """))
    with op.batch_alter_table("recipe_components") as batch:
        batch.alter_column("unit_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("net_quantity", existing_type=sa.Numeric(18, 6), nullable=False)
        batch.alter_column("gross_quantity", existing_type=sa.Numeric(18, 6), nullable=False)

    op.create_table(
        "recipe_cost_calculations",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("cost_before_waste", sa.Numeric(18, 6), nullable=False), sa.Column("waste_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False), sa.Column("cost_per_yield_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False), sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_table(
        "production_batches",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("output_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("lot_code", sa.String(80), nullable=False), sa.Column("planned_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(18, 6), nullable=False), sa.Column("actual_waste_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("branch_id", "lot_code", name="uq_production_batch_branch_lot"),
    )
    op.create_table(
        "order_line_consumption_snapshots",
        sa.Column("order_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("recipe_version", sa.Integer(), nullable=False), sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False), sa.Column("modifiers", sa.JSON(), nullable=False),
        sa.Column("total_theoretical_cost", sa.Numeric(18, 6), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("order_line_consumption_snapshots")
    op.drop_table("production_batches")
    op.drop_table("recipe_cost_calculations")
    with op.batch_alter_table("recipe_components") as batch:
        batch.drop_constraint("fk_recipe_components_unit", type_="foreignkey")
        for column in ("notes", "sort_order", "gross_quantity", "waste_rate", "net_quantity", "unit_id"):
            batch.drop_column(column)
        batch.alter_column("quantity_base_units", existing_type=sa.Numeric(18, 6), type_=sa.Integer(), nullable=False)
    with op.batch_alter_table("recipes") as batch:
        batch.drop_constraint("uq_recipes_output_item_version", type_="unique")
        batch.drop_constraint("fk_recipes_branch", type_="foreignkey")
        batch.drop_constraint("fk_recipes_output_item", type_="foreignkey")
        for column in ("updated_at", "valid_to", "valid_from", "recipe_type", "branch_id", "output_item_id"):
            batch.drop_column(column)
        batch.alter_column("yield_quantity", existing_type=sa.Numeric(18, 6), type_=sa.Integer(), nullable=False)
        batch.alter_column("product_id", existing_type=sa.String(36), nullable=False)
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :id").bindparams(id=PRODUCTION_PERMISSION_ID))
    op.execute(sa.text("DELETE FROM permissions WHERE id = :id").bindparams(id=PRODUCTION_PERMISSION_ID))

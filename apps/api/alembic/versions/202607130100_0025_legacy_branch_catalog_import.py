"""legacy branch catalog import

Revision ID: 0025_legacy_branch_catalog_import
Revises: 0024_branch_admin_scope
Create Date: 2026-07-13 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_legacy_branch_catalog_import"
down_revision: str | None = "0024_branch_admin_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column(
                "catalog_scope", sa.String(24), nullable=False, server_default="organization"
            )
        )
        batch.add_column(sa.Column("source_branch_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_products_source_branch_id", "branches", ["source_branch_id"], ["id"]
        )

    with op.batch_alter_table("inventory_items") as batch:
        batch.add_column(sa.Column("category_name", sa.String(120), nullable=True))
        batch.add_column(
            sa.Column(
                "catalog_scope", sa.String(24), nullable=False, server_default="organization"
            )
        )
        batch.add_column(sa.Column("source_branch_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_inventory_items_source_branch_id", "branches", ["source_branch_id"], ["id"]
        )

    op.create_table(
        "legacy_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("source_system", sa.String(80), nullable=False),
        sa.Column("manifest_checksum", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="loading"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "branch_id",
            "source_system",
            "manifest_checksum",
            name="uq_legacy_import_batch_manifest",
        ),
    )
    op.create_table(
        "legacy_import_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id", sa.String(36), sa.ForeignKey("legacy_import_batches.id"), nullable=False
        ),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=True),
        sa.Column("target_entity_type", sa.String(80), nullable=True),
        sa.Column("target_entity_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "batch_id", "entity_type", "source_key", name="uq_legacy_import_record_source"
        ),
    )
    op.create_index(
        "ix_legacy_import_records_batch_status",
        "legacy_import_records",
        ["batch_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_legacy_import_records_batch_status", table_name="legacy_import_records")
    op.drop_table("legacy_import_records")
    op.drop_table("legacy_import_batches")

    with op.batch_alter_table("inventory_items") as batch:
        batch.drop_constraint("fk_inventory_items_source_branch_id", type_="foreignkey")
        batch.drop_column("source_branch_id")
        batch.drop_column("catalog_scope")
        batch.drop_column("category_name")

    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("fk_products_source_branch_id", type_="foreignkey")
        batch.drop_column("source_branch_id")
        batch.drop_column("catalog_scope")

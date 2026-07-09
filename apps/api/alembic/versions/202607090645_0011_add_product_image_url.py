# ruff: noqa: E501
"""add product image url

Revision ID: 0011_add_product_image_url
Revises: 0010_pos_advanced_features
Create Date: 2026-07-09 06:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0011_add_product_image_url'
down_revision: str | None = '0010_pos_advanced_features'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('products', sa.Column('image_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'image_url')

"""line_items.product_image_url — Shopify urun gorseli cache

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("line_items", sa.Column("product_image_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("line_items", "product_image_url")

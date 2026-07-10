"""Zamanlanmış ürün yayını: catalog_products.publish_at

Revision ID: r8l9u0v1w2x3
Revises: q7k8t9u0v1w2
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "r8l9u0v1w2x3"
down_revision = "q7k8t9u0v1w2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products",
                  sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_products", "publish_at")

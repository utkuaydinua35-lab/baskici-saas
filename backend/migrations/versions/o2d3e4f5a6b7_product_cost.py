"""kar marji raporu — catalog_products.cost_price (birim maliyet)

Maliyet urun bazli; bos birakilirsa magaza ayarindaki varsayilan birim
maliyet kullanilir (config.profit_default_unit_cost).

Revision ID: o2d3e4f5a6b7
Revises: n1c2d3e4f5a6
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "o2d3e4f5a6b7"
down_revision = "n1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column(
        "cost_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_products", "cost_price")

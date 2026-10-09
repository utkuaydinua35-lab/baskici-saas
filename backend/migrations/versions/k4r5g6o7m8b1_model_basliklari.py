"""couple ürün: kılıf başına model seçici başlığı

Revision ID: k4r5g6o7m8b1
Revises: d1o0s0y0a1k2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "k4r5g6o7m8b1"
down_revision = "d1o0s0y0a1k2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column("model_basliklari", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_products", "model_basliklari")

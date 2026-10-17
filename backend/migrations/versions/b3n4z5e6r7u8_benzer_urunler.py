"""catalog_products.benzer_slugs + benzer_koleksiyonlar — ürün sayfasında
"Bu ürüne benzer ürünler" (elle ürün ve/veya koleksiyon seçimi)

Revision ID: b3n4z5e6r7u8
Revises: s7h8o9p0f1y2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b3n4z5e6r7u8"
down_revision = "s7h8o9p0f1y2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column("benzer_slugs", JSONB, nullable=True))
    op.add_column("catalog_products", sa.Column("benzer_koleksiyonlar", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_products", "benzer_koleksiyonlar")
    op.drop_column("catalog_products", "benzer_slugs")

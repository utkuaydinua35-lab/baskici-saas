"""varyant görseli eşleştirme, koleksiyonlu cross-sell, koleksiyon görseli kırpma

- catalog_products.varyant_gorsel: ürün sayfasında varyant seçilince eşleşen
  görsel öne gelsin mi (ürün başına açılır)
- catalog_images.varyant_anahtarlari: görselin bağlı olduğu varyantların
  model_key'leri (bir görsel birden çok varyanta; set yeniden senkronlansa da
  bağ kopmaz — varyant id'si değil anahtar tutulur)
- catalog_products.cross_sell_koleksiyonlar: sepette önerilecek koleksiyonlar
  (vitrinde koleksiyonun ÜRÜNLERİ olarak gösterilir)
- catalog_collections.gorsel_kirp: koleksiyon görselinin oranı ve kırpımı
  {"oran": "16:9", "x": 50, "y": 50, "zoom": 1}

Revision ID: v8a9r0g1o2r3
Revises: o7z8u9r0n1k2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "v8a9r0g1o2r3"
down_revision = "o7z8u9r0n1k2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column(
        "varyant_gorsel", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("catalog_images", sa.Column("varyant_anahtarlari", JSONB, nullable=True))
    op.add_column("catalog_products", sa.Column("cross_sell_koleksiyonlar", JSONB, nullable=True))
    op.add_column("catalog_collections", sa.Column("gorsel_kirp", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_collections", "gorsel_kirp")
    op.drop_column("catalog_products", "cross_sell_koleksiyonlar")
    op.drop_column("catalog_images", "varyant_anahtarlari")
    op.drop_column("catalog_products", "varyant_gorsel")

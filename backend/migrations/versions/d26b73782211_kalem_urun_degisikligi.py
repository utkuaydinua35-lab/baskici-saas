"""müşterinin ÜRÜN değişikliği — kalemde kalıcı kayıt

Revision ID: d26b73782211
Revises: a2bc4551a2ff

⚠ NEDEN AYRI SÜTUN, raw DEĞİL: Shopify senkronu kalemin product_id, title,
properties ve raw alanlarını HER senkronda Shopify'daki haliyle ezer. Müşteri
ürününü değiştirdiğinde bu bilgi raw'a yazılsaydı ilk senkronda kaybolur,
"tasarım bekliyor" kilidi kalkar ve kalem ESKİ tasarımla yeniden kalıba girerdi
(#11701: kişiye özel fotoğraflı kılıf, müşteri başka tasarım seçmişti).
Uygulamaya ait sütunlara senkron dokunmaz (orders._LI_APP_FIELDS).
"""
from alembic import op

revision = "d26b73782211"
down_revision = "a2bc4551a2ff"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE line_items ADD COLUMN IF NOT EXISTS urun_degisikligi JSONB")


def downgrade():
    op.execute("ALTER TABLE line_items DROP COLUMN IF EXISTS urun_degisikligi")

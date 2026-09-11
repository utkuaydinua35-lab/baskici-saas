"""şema kayması — canlıya ELLE eklenmiş iki destek sütunu migration'a alındı

Revision ID: b80e50baad93
Revises: f3c4d5e6a7b8

⚠ NEDEN: model ve canlı veritabanı `support_threads.customer_name` ile
`support_messages.is_read_by_admin` sütunlarını içeriyordu ama bunları ekleyen
migration YOKTU — canlıya elle eklenmişler. Sonuç: migration'lardan sıfırdan
kurulan HER veritabanında (yeni sunucu, CI, felaket sonrası kurulum) Destek
sayfası `UndefinedColumn` ile 500 veriyordu. Yerel geliştirme veritabanında
tam olarak bu görüldü.

IF NOT EXISTS: canlıda sütunlar zaten var — orada hiçbir şey değişmez.
Tipler canlıdan okundu: varchar(200) NULL · boolean NOT NULL DEFAULT false.
"""
from alembic import op

revision = "b80e50baad93"
down_revision = "f3c4d5e6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE support_threads "
               "ADD COLUMN IF NOT EXISTS customer_name VARCHAR(200)")
    op.execute("ALTER TABLE support_messages "
               "ADD COLUMN IF NOT EXISTS is_read_by_admin BOOLEAN NOT NULL DEFAULT false")


def downgrade():
    # Canlıda bu sütunlar migration'dan ÖNCE vardı; geri almak veri siler.
    # Bilinçli olarak boş bırakıldı.
    pass

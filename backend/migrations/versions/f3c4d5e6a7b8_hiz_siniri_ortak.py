"""hız sınırı vuruşları — süreçler (worker'lar) arasında ORTAK sayaç

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5f6a7

⚠ NEDEN: public uçların hız sınırı süreç belleğinde tutuluyordu. İkinci uvicorn
worker'ı açıldığı gün her worker kendi sayacını tutacak ve IP başına hak worker
sayısı kadar KATLANACAKTI (giriş kodu 5/5 dk → 10/5 dk). Sayaç veritabanına
taşındı; tüm worker'lar aynı tabloyu sayar.
"""
from alembic import op

revision = "f3c4d5e6a7b8"
down_revision = "e2b3c4d5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS hiz_siniri_vuruslari (
            id BIGSERIAL PRIMARY KEY,
            anahtar VARCHAR(300) NOT NULL,
            zaman TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_hiz_siniri_anahtar_zaman "
               "ON hiz_siniri_vuruslari (anahtar, zaman)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS hiz_siniri_vuruslari")

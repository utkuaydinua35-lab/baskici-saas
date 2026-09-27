"""abonelik işletimi: ödeme kaydında komisyon dönemi + geri alma + platform ayarları

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-27

abonelik_odemeleri:
  ciro_bas / ciro_bit  — komisyonun hesaplandığı satış dönemi. Sabit ücret
                         PEŞİN (donem_bas..donem_bit), komisyon GEÇEN dönemin
                         satışından (Shopify faturasıyla aynı düzen); ikisi
                         farklı tarih aralıkları olduğu için ayrı tutulur.
  siparis_sayisi       — komisyona giren vitrin siparişi adedi (denetim için)
  ay_sayisi            — peşin ödenen ay
  onceki_bitis /       — ödeme active_until'ı ne idiyse neye çekti; yanlış
  yeni_bitis             girilen ödeme iptal edilince eski tarihe dönülür.

platform_ayarlari: anahtar → JSONB. İlk kullanım: kiracılara gösterilen
havale bilgileri (IBAN, alıcı adı, banka, açıklama notu).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("abonelik_odemeleri", sa.Column("ciro_bas", sa.Date(), nullable=True))
    op.add_column("abonelik_odemeleri", sa.Column("ciro_bit", sa.Date(), nullable=True))
    op.add_column("abonelik_odemeleri", sa.Column(
        "siparis_sayisi", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("abonelik_odemeleri", sa.Column(
        "ay_sayisi", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("abonelik_odemeleri", sa.Column("onceki_bitis", sa.Date(), nullable=True))
    op.add_column("abonelik_odemeleri", sa.Column("yeni_bitis", sa.Date(), nullable=True))

    op.create_table(
        "platform_ayarlari",
        sa.Column("anahtar", sa.String(50), primary_key=True),
        sa.Column("deger", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("platform_ayarlari")
    for kolon in ("yeni_bitis", "onceki_bitis", "ay_sayisi", "siparis_sayisi",
                  "ciro_bit", "ciro_bas"):
        op.drop_column("abonelik_odemeleri", kolon)

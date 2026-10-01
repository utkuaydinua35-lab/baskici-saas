"""vitrin arama kayıtları — "müşteriler ne aradı, bulamadı" raporu

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-10-02

Ürünler sayfasındaki her arama (yazarken öneriler DEĞİL) normalleştirilmiş
sorgu + sonuç sayısıyla yazılır. Panel Analitik'te sonuçsuz ve en çok aranan
kelimeler listelenir: hangi tasarımın/modelin eksik olduğunu gösterir.
Kişisel veri yok (IP, oturum tutulmaz); 90 günden eskiler budanır.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arama_kayitlari",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sorgu", sa.String(100), nullable=False),
        sa.Column("sonuc", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_arama_kayitlari_store_zaman", "arama_kayitlari", ["store_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_arama_kayitlari_store_zaman", table_name="arama_kayitlari")
    op.drop_table("arama_kayitlari")

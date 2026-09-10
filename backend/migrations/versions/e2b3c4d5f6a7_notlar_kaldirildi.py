"""notes tablosu kaldırıldı — bölüm paketleme + sipariş detayıyla değiştirildi

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6

Notlar bölümü, paketleme kuyruğu ve sipariş detay sayfası olgunlaşmadan önceki
"açık siparişler listesi" ihtiyacını karşılıyordu. Artık her ikisi de aynı işi
daha iyi yapıyor; içerik zaten siparişlerden OTOMATİK üretiliyordu, yani
tabloda türetilemeyen veri yok.

⚠ VERİ: kaldırma öncesi canlıda 13 kayıt vardı; hiçbirinde elle yazılmış içerik
(manual_content) YOKTU. Tek serbest not deneme metniydi ("123123", "asd").
downgrade tabloyu geri kurar ama İÇERİĞİ geri getirmez — içerik zaten
siparişlerden yeniden üretilebilirdi.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e2b3c4d5f6a7"
down_revision = "d1a2b3c4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("notes")


def downgrade():
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), index=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("dealer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dealers.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("note_type", sa.String(20), server_default="acik", index=True),
        sa.Column("baslik", sa.String(200)),
        sa.Column("auto_content", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("manual_content", sa.Text(), nullable=True),
        sa.Column("lines", postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_serbest", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

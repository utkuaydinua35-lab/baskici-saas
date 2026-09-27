"""line_items.paketleme_ayrildi_2 — çift kılıfın 2. yarısı için ayrı işaret

Çift kılıf paketlemede İKİ ürün olarak listeleniyor (kutuya iki kılıf girer).
Tek bir "ayrıldı" işareti iki yarıyı birbirine bağlıyordu: birini kenara
ayırmak diğerini de ayrılmış gösteriyordu.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
"""
from alembic import op
import sqlalchemy as sa

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("line_items", sa.Column(
        "paketleme_ayrildi_2", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("line_items", "paketleme_ayrildi_2")

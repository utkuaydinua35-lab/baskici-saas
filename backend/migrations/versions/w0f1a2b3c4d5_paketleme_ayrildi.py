"""line_items.paketleme_ayrildi — paketlemede "kenara ayrıldı" işareti

Siparişin tamamı hazır olmasa da hazırlanan kılıflar dükkanda ayrı bir yere
konuyor. Bu bayrak o ayrımı sistemde de gösterir; eksiği olan siparişlerde
hangi ürünün hazırlanıp kenara alındığı karışmasın.

Revision ID: w0f1a2b3c4d5
Revises: c7d8e9f0a1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "w0f1a2b3c4d5"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "line_items",
        sa.Column("paketleme_ayrildi", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("line_items", "paketleme_ayrildi")

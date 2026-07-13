"""design baski_dosyasi_yok flag (hazır mockup / temiz baskı dosyası yok)

Revision ID: w4r5s6t7u8v9
Revises: v3q4y5z6a7b8
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = "w4r5s6t7u8v9"
down_revision = "v3q4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "designs",
        sa.Column("baski_dosyasi_yok", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_designs_baski_dosyasi_yok", "designs", ["baski_dosyasi_yok"])
    # Geriye dönük: Ürün Stüdyosu'ndan gelen ama PDF (temiz baskı) olmayan tasarımlar
    # = hazır mockup / kılıflı görsel -> baskı dosyası yok. Kişiye özel / manuel görselleri
    # etkilemez (onlar /studio/ yolunda değil).
    op.execute(
        "UPDATE designs SET baski_dosyasi_yok = true "
        "WHERE file_path LIKE '%/studio/%' AND file_format <> 'pdf'"
    )
    op.alter_column("designs", "baski_dosyasi_yok", server_default=None)


def downgrade():
    op.drop_index("ix_designs_baski_dosyasi_yok", table_name="designs")
    op.drop_column("designs", "baski_dosyasi_yok")

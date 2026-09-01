"""designs.icerik_hash — ayni dosyanin mukerrer yuklenmesini onlemek icin

Revision ID: c6f7a8b9d0e1
Revises: b5e6f7a8c9d0
"""
from alembic import op
import sqlalchemy as sa

revision = "c6f7a8b9d0e1"
down_revision = "b5e6f7a8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("designs", sa.Column("icerik_hash", sa.String(length=64), nullable=True))
    # Arama HER ZAMAN store_id ile birlikte yapilir (bayiler arasi paylasim YOK).
    op.create_index("ix_designs_store_icerik_hash", "designs",
                    ["store_id", "icerik_hash"])


def downgrade() -> None:
    op.drop_index("ix_designs_store_icerik_hash", table_name="designs")
    op.drop_column("designs", "icerik_hash")

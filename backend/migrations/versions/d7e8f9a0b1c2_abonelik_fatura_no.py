"""abonelik ödemesine fatura numarası

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-09-27

Fatura çoğu zaman ödemeden SONRA kesilir; numara kayıt anında ya da sonradan
girilir (platform → Abonelik → geçmiş). Kiracı kendi ödeme geçmişinde görür.
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("abonelik_odemeleri", sa.Column("fatura_no", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("abonelik_odemeleri", "fatura_no")

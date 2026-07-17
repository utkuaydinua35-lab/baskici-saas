"""dealer transaction dekont (ödeme dekontu dosya yolu)

Revision ID: x5s6t7u8v9w0
Revises: w4r5s6t7u8v9
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "x5s6t7u8v9w0"
down_revision = "w4r5s6t7u8v9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dealer_transactions", sa.Column("dekont_path", sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column("dealer_transactions", "dekont_path")

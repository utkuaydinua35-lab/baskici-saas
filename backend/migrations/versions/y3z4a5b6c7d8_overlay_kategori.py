"""hazır şablonlara kategori (modül teması) alanı

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "y3z4a5b6c7d8"
down_revision = "x2y3z4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("design_overlays", sa.Column("kategori", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("design_overlays", "kategori")

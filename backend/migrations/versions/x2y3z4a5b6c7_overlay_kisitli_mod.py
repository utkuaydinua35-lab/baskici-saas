"""hazır şablonlarda kısıtlı mod — müşteri sadece tanımlı alanları doldurur

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "x2y3z4a5b6c7"
down_revision = "w1x2y3z4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("design_overlays", sa.Column(
        "mod", sa.String(10), nullable=False, server_default=sa.text("'serbest'")))
    op.add_column("design_overlays", sa.Column(
        "alanlar", postgresql.JSONB(), nullable=False,
        server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    op.drop_column("design_overlays", "alanlar")
    op.drop_column("design_overlays", "mod")

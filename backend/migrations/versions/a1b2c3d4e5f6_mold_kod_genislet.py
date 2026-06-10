"""mold kod ve kalip_kodu kolonlarini genislet (grup kodlari uzun)

Revision ID: a1b2c3d4e5f6
Revises: 9d6e3a2f7c1b
Create Date: 2026-06-09

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "9d6e3a2f7c1b"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("molds", "kod",
        existing_type=sa.String(length=20),
        type_=sa.String(length=200),
        existing_nullable=False)
    op.alter_column("mold_items", "kalip_kodu",
        existing_type=sa.String(length=20),
        type_=sa.String(length=200),
        existing_nullable=False)


def downgrade():
    op.alter_column("mold_items", "kalip_kodu",
        existing_type=sa.String(length=200),
        type_=sa.String(length=20),
        existing_nullable=False)
    op.alter_column("molds", "kod",
        existing_type=sa.String(length=200),
        type_=sa.String(length=20),
        existing_nullable=False)

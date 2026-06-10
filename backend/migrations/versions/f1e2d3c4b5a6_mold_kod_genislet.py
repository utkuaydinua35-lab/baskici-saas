"""mold kod ve kalip_kodu kolonlarini genislet (grup kodlari uzun)

Revision ID: f1e2d3c4b5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-06-10

"""
from alembic import op
import sqlalchemy as sa

revision = "f1e2d3c4b5a6"
down_revision = "a7b8c9d0e1f2"
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

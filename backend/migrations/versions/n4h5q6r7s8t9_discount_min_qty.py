"""Miktar koşullu indirim: discount_codes.min_quantity

Revision ID: n4h5q6r7s8t9
Revises: m3g4p5q6r7s8
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "n4h5q6r7s8t9"
down_revision = "m3g4p5q6r7s8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discount_codes", sa.Column("min_quantity", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("discount_codes", "min_quantity")

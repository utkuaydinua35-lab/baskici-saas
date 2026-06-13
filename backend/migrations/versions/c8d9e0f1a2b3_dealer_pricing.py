"""dealer unit_price + shipping_fee

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dealers", sa.Column("unit_price", sa.Numeric(12, 2), server_default="0", nullable=False))
    op.add_column("dealers", sa.Column("shipping_fee", sa.Numeric(12, 2), server_default="0", nullable=False))


def downgrade():
    op.drop_column("dealers", "shipping_fee")
    op.drop_column("dealers", "unit_price")

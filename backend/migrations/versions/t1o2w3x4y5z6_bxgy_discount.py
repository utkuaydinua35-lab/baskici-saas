"""X Al Y Öde kampanyaları: discount_codes.buy_x/pay_y

Revision ID: t1o2w3x4y5z6
Revises: s0n1v2w3x4y5
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "t1o2w3x4y5z6"
down_revision = "s0n1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discount_codes", sa.Column("buy_x", sa.Integer(), nullable=True))
    op.add_column("discount_codes", sa.Column("pay_y", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("discount_codes", "pay_y")
    op.drop_column("discount_codes", "buy_x")

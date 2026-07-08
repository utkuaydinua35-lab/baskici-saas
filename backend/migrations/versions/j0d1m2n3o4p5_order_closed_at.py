"""siparis arsiv durumu: orders.closed_at

Revision ID: j0d1m2n3o4p5
Revises: i9c0l1m2n3o4
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa


revision = "j0d1m2n3o4p5"
down_revision = "i9c0l1m2n3o4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_closed_at", "orders", ["closed_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_closed_at", table_name="orders")
    op.drop_column("orders", "closed_at")

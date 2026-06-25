"""orders.kargo_deadline — kargo soz tarihi (SLA)

Revision ID: i3c4d5e6f7a8
Revises: h2b3c4d5e6f7
Create Date: 2026-06-25

"""
from alembic import op
import sqlalchemy as sa

revision = "i3c4d5e6f7a8"
down_revision = "h2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("kargo_deadline", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_kargo_deadline", "orders", ["kargo_deadline"])


def downgrade() -> None:
    op.drop_index("ix_orders_kargo_deadline", table_name="orders")
    op.drop_column("orders", "kargo_deadline")

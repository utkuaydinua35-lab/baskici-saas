"""orders.deleted_at — soft delete (geri al)

Revision ID: h2b3c4d5e6f7
Revises: g1a2b3c4d5e6
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa

revision = "h2b3c4d5e6f7"
down_revision = "g1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_deleted_at", "orders", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_deleted_at", table_name="orders")
    op.drop_column("orders", "deleted_at")

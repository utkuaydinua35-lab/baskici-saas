"""order kalip_haric (kalip olusturucudan haric tut)

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-17

"""
from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("kalip_haric", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_orders_kalip_haric", "orders", ["kalip_haric"])


def downgrade() -> None:
    op.drop_index("ix_orders_kalip_haric", table_name="orders")
    op.drop_column("orders", "kalip_haric")

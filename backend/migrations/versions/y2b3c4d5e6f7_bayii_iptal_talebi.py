"""Bayi iptal talebi — orders.bayii_iptal_talebi + sebep

Revision ID: y2b3c4d5e6f7
Revises: x1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa

revision = "y2b3c4d5e6f7"
down_revision = "x1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column(
        "bayii_iptal_talebi", sa.Boolean(), nullable=False,
        server_default=sa.text("false")))
    op.add_column("orders", sa.Column("bayii_iptal_sebep", sa.Text(), nullable=True))
    op.create_index("ix_orders_bayii_iptal_talebi", "orders", ["bayii_iptal_talebi"])


def downgrade() -> None:
    op.drop_index("ix_orders_bayii_iptal_talebi", table_name="orders")
    op.drop_column("orders", "bayii_iptal_sebep")
    op.drop_column("orders", "bayii_iptal_talebi")

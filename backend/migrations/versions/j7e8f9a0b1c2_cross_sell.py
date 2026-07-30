"""catalog_products.cross_sell_slugs — sepette 'bunu da ekleyin' onerileri

Revision ID: j7e8f9a0b1c2
Revises: i6d7e8f9a0b1
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "j7e8f9a0b1c2"
down_revision = "i6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products",
                  sa.Column("cross_sell_slugs", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_products", "cross_sell_slugs")

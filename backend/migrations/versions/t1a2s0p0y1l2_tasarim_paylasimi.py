"""stores.tasarim_grubu — mağazalar arası tasarım paylaşımı

Aynı atölyede aynı grup adını taşıyan mağazalar birbirinin tasarımlarını
kullanır (Shopify mağazası + kendi vitrini tek havuz).

Revision ID: t1a2s0p0y1l2
Revises: v5t6o7r8m9n0
"""
from alembic import op
import sqlalchemy as sa

revision = "t1a2s0p0y1l2"
down_revision = "v5t6o7r8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("tasarim_grubu", sa.String(50), nullable=True))
    op.create_index("ix_stores_tasarim_grubu", "stores", ["tasarim_grubu"])


def downgrade() -> None:
    op.drop_index("ix_stores_tasarim_grubu", table_name="stores")
    op.drop_column("stores", "tasarim_grubu")

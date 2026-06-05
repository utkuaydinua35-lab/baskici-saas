"""Mold.store_id nullable + MoldItem.store_id ekle (multi-store)

Revision ID: 8c5d2f1e9a4b
Revises: 7b4c8a9d3e2f
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '8c5d2f1e9a4b'
down_revision = '7b4c8a9d3e2f'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Mold.store_id → nullable yap (multi-store kalıplar için NULL)
    op.alter_column('molds', 'store_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    # 2) MoldItem.store_id → yeni nullable kolon (her slot'un hangi mağazadan geldiği)
    op.add_column(
        'mold_items',
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_mold_items_store_id',
        'mold_items', 'stores',
        ['store_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_mold_items_store_id', 'mold_items', ['store_id'])

    # 3) Mevcut MoldItem'lara store_id doldur: parent mold'un store_id'sini al
    op.execute("""
        UPDATE mold_items mi
        SET store_id = m.store_id
        FROM molds m
        WHERE mi.mold_id = m.id AND m.store_id IS NOT NULL
    """)


def downgrade():
    op.drop_index('ix_mold_items_store_id', 'mold_items')
    op.drop_constraint('fk_mold_items_store_id', 'mold_items', type_='foreignkey')
    op.drop_column('mold_items', 'store_id')
    # Mold.store_id → tekrar NOT NULL (DİKKAT: NULL satır varsa fail)
    op.execute("UPDATE molds SET store_id = (SELECT id FROM stores LIMIT 1) WHERE store_id IS NULL")
    op.alter_column('molds', 'store_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)

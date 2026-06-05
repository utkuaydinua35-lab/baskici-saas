"""aski_items tablosu

Revision ID: 7b4c8a9d3e2f
Revises: 5e1a3f8b2d6c
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '7b4c8a9d3e2f'
down_revision = '5e1a3f8b2d6c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'aski_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('design_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('variation', sa.String(20), nullable=True),
        sa.Column('quantity', sa.Integer, nullable=False, server_default='1'),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('source_line_item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['design_id'], ['designs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_line_item_id'], ['line_items.id'], ondelete='SET NULL'),
        sa.UniqueConstraint(
            'tenant_id', 'store_id', 'design_id', 'model', 'variation',
            name='uq_aski_design_model_var',
        ),
    )
    op.create_index('ix_aski_items_tenant_id', 'aski_items', ['tenant_id'])
    op.create_index('ix_aski_items_store_id', 'aski_items', ['store_id'])
    op.create_index('ix_aski_items_design_id', 'aski_items', ['design_id'])
    op.create_index('ix_aski_items_model', 'aski_items', ['model'])


def downgrade():
    op.drop_index('ix_aski_items_model', 'aski_items')
    op.drop_index('ix_aski_items_design_id', 'aski_items')
    op.drop_index('ix_aski_items_store_id', 'aski_items')
    op.drop_index('ix_aski_items_tenant_id', 'aski_items')
    op.drop_table('aski_items')

"""mold_status_history.mold_id nullable + ON DELETE SET NULL

Revision ID: 5e1a3f8b2d6c
Revises: 4c37232d7a34
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '5e1a3f8b2d6c'
down_revision = '4c37232d7a34'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('mold_status_history_mold_id_fkey', 'mold_status_history', type_='foreignkey')
    op.alter_column('mold_status_history', 'mold_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    nullable=True)
    op.create_foreign_key(
        'mold_status_history_mold_id_fkey',
        'mold_status_history', 'molds',
        ['mold_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('mold_status_history_mold_id_fkey', 'mold_status_history', type_='foreignkey')
    op.alter_column('mold_status_history', 'mold_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    nullable=False)
    op.create_foreign_key(
        'mold_status_history_mold_id_fkey',
        'mold_status_history', 'molds',
        ['mold_id'], ['id'],
        ondelete='CASCADE'
    )

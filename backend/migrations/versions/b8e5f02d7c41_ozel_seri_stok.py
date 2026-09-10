"""ozel_seri_stok — BERNZ Special stok bulundurulan modeller

Special yalniz birkac modelde stok tutuyor; musteriye 300+ modelin tamamini
sunmak uretilemeyecek siparise donusur. Liste tenant basina tutulur ve ilk
okumada varsayilanla doldurulur (bkz. services/ozel_seri.py).

Revision ID: b8e5f02d7c41
Revises: a7d4e91c2b30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8e5f02d7c41'
down_revision: Union[str, None] = 'a7d4e91c2b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ozel_seri_stok',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('sira', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('stokta', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'model', name='uq_ozel_seri_tenant_model'),
    )
    op.create_index(op.f('ix_ozel_seri_stok_tenant_id'), 'ozel_seri_stok', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('ozel_seri_stok')

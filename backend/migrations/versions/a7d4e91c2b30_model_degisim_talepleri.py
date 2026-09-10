"""model_degisim_talepleri + molds.uyarilar

Stok yoklugu nedeniyle kaliptan cikarilan kalem icin musteriye WhatsApp'tan
gonderilen, 12 saat gecerli "telefon modelini degistir" baglantisi.

molds.uyarilar: musteri modelini degistirdiginde kalem kaliptan CEKILIYOR;
baskicinin kalibi actiginda bunu gormesi gerekiyor, yoksa cope gidecek bir
kilif basiliyor.

Revision ID: a7d4e91c2b30
Revises: f9c7f3491b4b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7d4e91c2b30'
down_revision: Union[str, None] = 'f9c7f3491b4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('molds', sa.Column(
        'uyarilar', postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"), nullable=False))

    op.create_table(
        'model_degisim_talepleri',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('line_item_id', sa.UUID(), nullable=True),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('kalip_turu', sa.String(length=10), nullable=False),
        sa.Column('urun_adi', sa.String(length=300), nullable=True),
        sa.Column('mevcut_model', sa.String(length=100), nullable=True),
        sa.Column('durum', sa.String(length=20), nullable=False),
        sa.Column('secilen_model', sa.String(length=100), nullable=True),
        sa.Column('secilen_varyasyon', sa.String(length=20), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('uygulandi_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['line_item_id'], ['line_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_model_degisim_talepleri_tenant_id'),
                    'model_degisim_talepleri', ['tenant_id'])
    op.create_index(op.f('ix_model_degisim_talepleri_order_id'),
                    'model_degisim_talepleri', ['order_id'])
    op.create_index(op.f('ix_model_degisim_talepleri_token'),
                    'model_degisim_talepleri', ['token'], unique=True)


def downgrade() -> None:
    op.drop_table('model_degisim_talepleri')
    op.drop_column('molds', 'uyarilar')

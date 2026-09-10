"""adres_degisim_talepleri

Musteriye gonderilen tek kullanimlik "teslimat adresini degistir" baglantisi.
Model degisikliginden daha riskli: yanlis kisi degistirirse paket ona gider.
Baglanti kisa omurlu ve tek kullanimlik; operator tarafindan siparisteki
telefona gonderiliyor.

Revision ID: c9f1a3d84e27
Revises: b8e5f02d7c41
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c9f1a3d84e27'
down_revision: Union[str, None] = 'b8e5f02d7c41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'adres_degisim_talepleri',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('durum', sa.String(length=20), nullable=False),
        sa.Column('eski_adres', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('yeni_adres', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pazarlama_izni', sa.Boolean(),
                  server_default=sa.text('false'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('uygulandi_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_adres_degisim_talepleri_tenant_id'),
                    'adres_degisim_talepleri', ['tenant_id'])
    op.create_index(op.f('ix_adres_degisim_talepleri_order_id'),
                    'adres_degisim_talepleri', ['order_id'])
    op.create_index(op.f('ix_adres_degisim_talepleri_token'),
                    'adres_degisim_talepleri', ['token'], unique=True)


def downgrade() -> None:
    op.drop_table('adres_degisim_talepleri')

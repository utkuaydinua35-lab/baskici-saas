"""device_tokens (native uygulama bildirim jetonu)

Uygulamaya bildirim APNs (iOS) / FCM (Android) uzerinden gider; tarayicinin
push_subscriptions tablosu orada kullanilamaz. Ayni kisi hem tarayicidan hem
uygulamadan bildirim alabilsin diye iki tablo AYRI duruyor.

NOT: autogenerate bu surumde tabloyla ilgisi olmayan pek cok fark daha
uretmisti (eski indeksler, gecmiste elle atilmis NOT NULL'lar). Onlar bilincli
olarak CIKARILDI — bu migration yalnizca yeni tabloyu olusturur.

Revision ID: f9c7f3491b4b
Revises: fe2facc5eb60
Create Date: 2026-09-09 15:07:27.209652
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f9c7f3491b4b'
down_revision: Union[str, None] = 'fe2facc5eb60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=10), nullable=False),
        sa.Column('device_name', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_device_tokens_tenant_id'), 'device_tokens', ['tenant_id'])
    op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_device_tokens_user_id'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_tenant_id'), table_name='device_tokens')
    op.drop_table('device_tokens')

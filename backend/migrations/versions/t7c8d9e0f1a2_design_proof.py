"""studyo tasarimi — rotus sonrasi numune gorseli (proof_path)

Musteri onayinda studyo onizlemesi yerine operatorun hazirladigi numune
gosterilir; yoksa onizlemeye dusulur.

Revision ID: t7c8d9e0f1a2
Revises: s6b7c8d9e0f1
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op

revision = "t7c8d9e0f1a2"
down_revision = "s6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_designs", sa.Column("proof_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("customer_designs", "proof_path")

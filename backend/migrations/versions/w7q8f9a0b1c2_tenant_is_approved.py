"""tenant onay: tenants.is_approved (yeni kayit yonetici onayi bekler)

Revision ID: w7q8f9a0b1c2
Revises: v6p7e8f9a0b1
Create Date: 2026-06-29

"""
from alembic import op
import sqlalchemy as sa

revision = "w7q8f9a0b1c2"
down_revision = "v6p7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mevcut atolyeler onayli kalsin (server_default true); yeni self-servis kayitlar
    # router'da is_approved=False olarak olusturulur.
    op.add_column("tenants", sa.Column(
        "is_approved", sa.Boolean(), server_default=sa.text("true"), nullable=False))


def downgrade() -> None:
    op.drop_column("tenants", "is_approved")

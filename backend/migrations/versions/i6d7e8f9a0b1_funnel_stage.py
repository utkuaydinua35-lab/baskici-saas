"""terk edilme asamasi takibi — presence.stage + checkout_sessions.last_stage

Musteri nerede vazgecti sorusuna cevap: sepete ekledi mi, odeme sayfasina
geldi mi, formu doldurdu mu, saglayiciya yonlendi mi. Shopify'da yok.

Revision ID: i6d7e8f9a0b1
Revises: g4b5c6d7e8f9
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = "i6d7e8f9a0b1"
down_revision = "g4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ziyaretçi oturumunun ulaştığı EN İLERİ aşama (geri gitmez)
    op.add_column("storefront_presence",
                  sa.Column("stage", sa.String(30), nullable=True))
    op.add_column("storefront_presence",
                  sa.Column("stage_at", sa.DateTime(timezone=True), nullable=True))
    # Terk edilen ödeme oturumunun son aşaması (checkout içi ilerleme)
    op.add_column("checkout_sessions",
                  sa.Column("last_stage", sa.String(30), nullable=True))
    op.add_column("checkout_sessions",
                  sa.Column("last_stage_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("checkout_sessions", "last_stage_at")
    op.drop_column("checkout_sessions", "last_stage")
    op.drop_column("storefront_presence", "stage_at")
    op.drop_column("storefront_presence", "stage")

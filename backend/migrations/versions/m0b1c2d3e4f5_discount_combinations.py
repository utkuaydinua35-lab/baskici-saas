"""indirim kombinasyonlari — discount_codes.combinable + sessions.discount_breakdown

Birlesebilir indirim: sepet indirimi (%/TL/XalYode) ile kargo indirimi ayni
anda uygulanabilir. Dokum JSONB'de tutulur; kullanim sayaci uygulanan TUM
kuponlar icin artar.

Revision ID: m0b1c2d3e4f5
Revises: l9a0b1c2d3e4
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "m0b1c2d3e4f5"
down_revision = "l9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discount_codes", sa.Column(
        "combinable", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("checkout_sessions", sa.Column(
        "discount_breakdown", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("checkout_sessions", "discount_breakdown")
    op.drop_column("discount_codes", "combinable")

"""Otomatik indirimler: discount_codes.is_automatic

Revision ID: h8b9k0l1m2n3
Revises: g7a8j9k0l1m2
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "h8b9k0l1m2n3"
down_revision = "g7a8j9k0l1m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discount_codes",
        sa.Column("is_automatic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("discount_codes", "is_automatic")

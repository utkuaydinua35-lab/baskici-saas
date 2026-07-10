"""Ürün videosu: catalog_products.video_url

Revision ID: u2p3x4y5z6a7
Revises: t1o2w3x4y5z6
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "u2p3x4y5z6a7"
down_revision = "t1o2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column("video_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_products", "video_url")

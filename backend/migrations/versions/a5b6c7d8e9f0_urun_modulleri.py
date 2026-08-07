"""hazır tasarım modüllerinin ürüne bağlanması

Revision ID: a5b6c7d8e9f0
Revises: z4a5b6c7d8e9
Create Date: 2026-08-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a5b6c7d8e9f0"
down_revision = "z4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column(
        "studio_overlays", postgresql.JSONB(), nullable=False,
        server_default=sa.text("'[]'::jsonb")))
    op.add_column("design_overlays", sa.Column(
        "sadece_urunde", sa.Boolean(), nullable=False,
        server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("design_overlays", "sadece_urunde")
    op.drop_column("catalog_products", "studio_overlays")
